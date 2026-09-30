import time

import requests
import speech_recognition as sr

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
        set_status("Listening")
        recognizer.adjust_for_ambient_noise(source, duration=0.5)
        audio = recognizer.listen(source, timeout=timeout, phrase_time_limit=phrase_time_limit)
    set_status("Thinking")
    return recognizer.recognize_google(audio, language="en-US")


def voice_cycle(conversation_history, set_status):
    try:
        text = _listen_once(set_status, timeout=10, phrase_time_limit=5)
    except sr.UnknownValueError:
        print("I didn't understand what you said. Try again.")
        return
    except sr.WaitTimeoutError:
        return
    except sr.RequestException as error:
        print("Speech recognition service unavailable:", error)
        return

    print("Google heard the wake word:", repr(text))

    if not is_wake_word(text):
        speak("I don't know that command yet.", set_status)
        return

    speak("Yes? I'm listening.", set_status)

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
            speak("I can't reach the speech recognition service right now.", set_status)
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
                speak(answer, set_status)

            elif result.kind == "INCOMPLETE":
                print("Incomplete command:", repr(command_text))
                speak(result.text, set_status)

            else:
                print("Final answer:", repr(result.text))
                speak(result.text, set_status)

        except requests.RequestException as error:
            print("Ollama request failed:", error)
            speak("I can't reach my local language model right now.", set_status)


def voice_loop(conversation_history, set_status):
    while True:
        try:
            voice_cycle(conversation_history, set_status)
        except Exception as error:
            print("Unexpected error in voice cycle:", error)
            set_status("Error - retrying")
            time.sleep(2)
