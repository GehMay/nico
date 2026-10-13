import time

import requests
import speech_recognition as sr

import state
from desktop_app import hide_desktop_window, show_desktop_window
import speaker_id
import speech_to_text
import wake_word
from commands import handle_command, resolve_clarification
from config import (
    ENROLL_VOICE_TRIGGERS,
    RECOGNIZER_PAUSE_THRESHOLD_SECONDS,
    WAKE_WORD_ALIASES,
    WAKE_WORDS,
)
from text_utils import normalize_text
from tts import speak

recognizer = sr.Recognizer()
recognizer.pause_threshold = RECOGNIZER_PAUSE_THRESHOLD_SECONDS


def is_wake_word(text):
    normalized = normalize_text(text)
    if not normalized:
        return False

    tokens = normalized.split()
    for token in tokens:
        if token in WAKE_WORDS:
            return True
        alias = WAKE_WORD_ALIASES.get(token)
        if alias in WAKE_WORDS:
            return True

    return False


def _listen_once(set_status, timeout, phrase_time_limit=None, verify_speaker=False):
    with sr.Microphone() as source:
        set_status("Ouvindo")
        recognizer.adjust_for_ambient_noise(source, duration=0.5)
        audio = recognizer.listen(source, timeout=timeout, phrase_time_limit=phrase_time_limit)
    if not state.is_mic_enabled():
        set_status("Pausado")
        return ""

    pcm16k = audio.get_raw_data(convert_rate=16000, convert_width=2)

    if verify_speaker and speaker_id.has_profile():
        if speaker_id.matches_profile(pcm16k) is False:
            print("Áudio ignorado: a voz não corresponde ao perfil cadastrado.")
            return ""

    set_status("Pensando")

    if speech_to_text.is_available():
        # Whisper local entende nomes/palavras em inglês misturados na
        # frase em português numa só passada - substitui a transcrição por
        # nuvem (Google) quando disponível.
        text = speech_to_text.transcribe_pcm16k(pcm16k)
        if text:
            return text
        raise sr.UnknownValueError()

    try:
        return recognizer.recognize_google(audio, language="pt-BR")
    except sr.UnknownValueError:
        # O português não entendeu nada - tenta em inglês antes de desistir.
        # Isso ajuda com nomes de empresas/produtos em inglês que não têm
        # nenhum encaixe fonético plausível em português (a API gratuita do
        # Google só aceita um idioma por chamada, não dá pra misturar os
        # dois numa frase só). Só usado se o Whisper local não estiver
        # disponível - é o caminho antigo, mantido como alternativa.
        return recognizer.recognize_google(audio, language="en-US")


def voice_cycle(conversation_history, set_status):
    if not wake_word.is_available():
        status = "Erro - configure a wake word local"
        if state.is_mic_enabled() or state.get_status() != status:
            state.set_mic_enabled(False)
            set_status(status)
            show_desktop_window()
        time.sleep(2)
        return

    if not state.is_mic_enabled():
        # Microfone pausado pelo botão do HUD - não abre o microfone nem
        # manda nada pra nuvem enquanto estiver assim.
        active_statuses = {
            "Pensando", "Falando", "Pesquisando", "Lendo documentos",
            "Aguardando aprovação", "Executando ação",
            "Erro - configure a wake word local",
            "Erro - falha na wake word local",
        }
        if state.get_status() not in active_statuses:
            set_status("Pausado")
        time.sleep(0.5)
        return

    try:
        activated = wake_word.listen_for_wake_word(set_status)
    except Exception as error:
        print("Local wake-word detection failed; microphone disabled without cloud fallback:", error)
        state.set_mic_enabled(False)
        set_status("Erro - falha na wake word local")
        show_desktop_window()
        return

    if not activated:
        set_status("Pausado")
        return

    show_desktop_window()

    speak("Sim, estou ouvindo.", set_status)

    while True:
        try:
            command_text = _listen_once(set_status, timeout=10, verify_speaker=True)
        except sr.WaitTimeoutError:
            print("No command for 10 seconds. Waiting for wake word.")
            if state.is_mic_enabled():
                hide_desktop_window()
            break
        except sr.UnknownValueError:
            print("I didn't understand that command.")
            continue
        except sr.RequestException as error:
            print("Speech recognition service unavailable:", error)
            speak("Não consigo acessar o serviço de reconhecimento de voz agora.", set_status)
            hide_desktop_window()
            break

        print("Google heard the command:", repr(command_text))

        if not command_text or not command_text.strip():
            if not state.is_mic_enabled():
                break
            continue

        if any(trigger in normalize_text(command_text) for trigger in ENROLL_VOICE_TRIGGERS):
            if speaker_id.is_available():
                speaker_id.enroll_from_microphone(set_status, speak)
            else:
                speak(
                    "Não consigo cadastrar sua voz agora - falta o modelo de "
                    "identificação de locutor.",
                    set_status,
                )
            continue

        try:
            result = handle_command(command_text, conversation_history)

            if result.kind in {"RESEARCH_CLARIFY", "DOCUMENT_UPDATE_CLARIFY"}:
                while result.kind in {"RESEARCH_CLARIFY", "DOCUMENT_UPDATE_CLARIFY"}:
                    speak(result.text, set_status)
                    try:
                        reply_text = _listen_once(set_status, timeout=20)
                    except (sr.WaitTimeoutError, sr.UnknownValueError, sr.RequestException):
                        result = None
                        break
                    result = handle_command(reply_text, conversation_history)

                if result is not None:
                    print("Final answer:", repr(result.text))
                    conversation_history.append((command_text, result.text))
                    speak(result.text, set_status)

            elif result.kind == "CLARIFY":
                speak(result.text, set_status)
                try:
                    reply_text = _listen_once(set_status, timeout=8)
                except (sr.WaitTimeoutError, sr.UnknownValueError, sr.RequestException):
                    reply_text = ""
                answer = resolve_clarification(
                    reply_text, result.candidates, command_text, conversation_history
                )
                print("Final answer:", repr(answer))
                conversation_history.append((command_text, answer))
                speak(answer, set_status)

            elif result.kind == "INCOMPLETE":
                print("Incomplete command:", repr(command_text))
                conversation_history.append((command_text, result.text))
                speak(result.text, set_status)

            else:
                print("Final answer:", repr(result.text))
                conversation_history.append((command_text, result.text))
                speak(result.text, set_status)

        except requests.RequestException as error:
            print("Ollama request failed:", error)
            speak("Não consigo acessar meu modelo de linguagem local agora.", set_status)


def voice_loop(conversation_history, set_status):
    while True:
        try:
            voice_cycle(conversation_history, set_status)
        except Exception as error:
            print("Unexpected error in voice cycle:", error)
            set_status("Erro - tentando novamente")
            time.sleep(2)
