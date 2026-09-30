import socket
import threading

import state
from config import REMINDER_CHECK_INTERVAL_SECONDS
from database import create_table
from desktop_app import open_desktop_window
from reminders import reminder_loop
from voice import voice_loop
from web_server import run_web_server

WEB_PORT = 5000


def _local_ip():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.connect(("8.8.8.8", 80))
        return sock.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        sock.close()


def main():
    create_table()

    voice_thread = threading.Thread(
        target=voice_loop,
        args=(state.conversation_history, state.set_status),
        daemon=True,
    )
    voice_thread.start()

    web_thread = threading.Thread(
        target=run_web_server,
        kwargs={"host": "0.0.0.0", "port": WEB_PORT},
        daemon=True,
    )
    web_thread.start()

    reminder_thread = threading.Thread(
        target=reminder_loop,
        args=(state.set_status, REMINDER_CHECK_INTERVAL_SECONDS),
        daemon=True,
    )
    reminder_thread.start()

    print(f"Web panel: http://localhost:{WEB_PORT}  (on your phone/tablet, same Wi-Fi: http://{_local_ip()}:{WEB_PORT})")

    open_desktop_window(f"http://127.0.0.1:{WEB_PORT}/")


if __name__ == "__main__":
    main()
