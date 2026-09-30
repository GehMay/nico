import socket
import time

import webview

WINDOW_TITLE = "Nico"
WINDOW_WIDTH = 480
WINDOW_HEIGHT = 820
BACKGROUND_COLOR = "#05060a"


def _wait_for_server(host, port, timeout=10):
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with socket.create_connection((host, port), timeout=0.5):
                return True
        except OSError:
            time.sleep(0.2)
    return False


def open_desktop_window(url, host="127.0.0.1", port=5000):
    _wait_for_server(host, port)
    webview.create_window(
        WINDOW_TITLE,
        url,
        width=WINDOW_WIDTH,
        height=WINDOW_HEIGHT,
        background_color=BACKGROUND_COLOR,
        min_size=(360, 600),
    )
    webview.start()
