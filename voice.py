import time

import requests
import speech_recognition as sr

import state
import wake_word
from commands import handle_command, resolve_clarification
from config import WAKE_WORD_ALIASES, WAKE_WORDS
from text_utils import normalize_text
from tts import speak

recognizer = sr.Recognizer()


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


def _listen_once(set_status, timeout, phrase_time_limit=None):
    with sr.Microphone() as source:
        set_status("Ouvindo")
        recognizer.adjust_for_ambient_noise(source, duration=0.5)
        audio = recognizer.listen(source, timeout=timeout, phrase_time_limit=phrase_time_limit)
    set_status("Pensando")
    return recognizer.recognize_google(audio, language="pt-BR")


def _cloud_wake_word_detected(set_status):
    """Detecta a wake word do jeito original (manda o áudio pro Google).
    Devolve True se detectou a wake word, False se não (silêncio, não
    entendeu, ou entendeu mas não era a wake word).
    """
    try:
        text = _listen_once(set_status, timeout=10, phrase_time_limit=5)
    except sr.UnknownValueError:
        print("I didn't understand what you said. Try again.")
        return False
    except sr.WaitTimeoutError:
        return False
    except sr.RequestException as error:
        print("Speech recognition service unavailable:", error)
        return False

    print("Google heard the wake word:", repr(text))

    if not is_wake_word(text):
        speak("Ainda não conheço esse comando.", set_status)
        return False

    return True


def voice_cycle(conversation_history, set_status):
    if not state.is_mic_enabled():
        # Microfone pausado pelo botão do HUD - não abre o microfone nem
        # manda nada pra nuvem enquanto estiver assim.
        set_status("Pausado")
        time.sleep(0.5)
        return

    if wake_word.is_available():
        try:
            wake_word.listen_for_wake_word(set_status)
        except Exception as error:
            print("Offline wake-word detection failed, falling back to cloud this time:", error)
            if not _cloud_wake_word_detected(set_status):
                return
    else:
        if not _cloud_wake_word_detected(set_status):
            return

    speak("Sim, estou ouvindo.", set_status)

    while True:
        try:
            command_text = _listen_once(set_status, timeout=10)
        except sr.WaitTimeoutError:
            print("No command for 10 seconds. Waiting for wake word.")
            break
        except sr.UnknownValueError:
            print("I didn't understand that command.")
            continue
        except sr.RequestException as error:
            print("Speech recognition service unavailable:", error)
            speak("Não consigo acessar o serviço de reconhecimento de voz agora.", set_status)
            break

        print("Google heard the command:", repr(command_text))

        if not command_text or not command_text.strip():
            continue

        try:
            result = handle_command(command_text, conversation_history)

            if result.kind == "CLARIFY":
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
