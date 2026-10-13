import threading

import state
from config import REMINDER_CHECK_INTERVAL_SECONDS, SECURITY_CHECK_INTERVAL_SECONDS
from database import create_table
from desktop_app import open_desktop_window, show_desktop_window
from reminders import reminder_loop
from security_monitor import security_monitor_loop
import speech_to_text
from voice import voice_loop
import wake_word
from web_server import run_web_server

WEB_PORT = 5000


def _start_background_services():
    voice_thread = threading.Thread(
        target=voice_loop,
        args=(state.conversation_history, state.set_status),
        daemon=True,
    )
    voice_thread.start()

    reminder_thread = threading.Thread(
        target=reminder_loop,
        args=(state.set_status, REMINDER_CHECK_INTERVAL_SECONDS),
        daemon=True,
    )
    reminder_thread.start()

    security_thread = threading.Thread(
        target=security_monitor_loop,
        args=(SECURITY_CHECK_INTERVAL_SECONDS, _show_security_alert),
        daemon=True,
    )
    security_thread.start()

    # Carrega o modelo Whisper antecipadamente - sem isso, o primeiro
    # comando real pagaria o custo de carregar o modelo (alguns segundos,
    # ou mais de um minuto se precisar baixá-lo na primeira vez) bem no
    # meio da fala do usuário.
    whisper_thread = threading.Thread(target=speech_to_text.preload, daemon=True)
    whisper_thread.start()


def _show_security_alert(message):
    if message.startswith("Norton e Firewall voltaram"):
        state.set_status(f"Proteção restaurada: {message}")
    else:
        state.set_status(f"Alerta de segurança: {message}")
    show_desktop_window()


def main():
    create_table()

    local_wake_ready = wake_word.is_available()
    if local_wake_ready:
        state.set_mic_enabled(True)
        state.set_status("Ouvindo")
    else:
        state.set_mic_enabled(False)
        state.set_status("Erro - configure a wake word local")

    web_thread = threading.Thread(
        target=run_web_server,
        kwargs={"host": "127.0.0.1", "port": WEB_PORT},
        daemon=True,
    )
    web_thread.start()

    open_desktop_window(
        f"http://127.0.0.1:{WEB_PORT}/",
        hidden=local_wake_ready,
        on_ready=_start_background_services,
    )


if __name__ == "__main__":
    main()
