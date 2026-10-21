import socket
import time
import webbrowser

import webview

WINDOW_TITLE = "Nico"
WINDOW_WIDTH = 500
WINDOW_HEIGHT = 235
BACKGROUND_COLOR = "#05060a"
_window = None
# Preenchido em open_desktop_window() - usado pelo botão "Memória" do HUD
# pra abrir a galáxia no navegador padrão, já que a janela compacta do HUD
# (sem bordas, 460x235, sempre no topo) não foi pensada pra mostrar um
# grafo grande - não dá pra "maximizar" essa janela, ela é assim de
# propósito, então a galáxia abre à parte, numa aba normal de navegador.
_memory_url = "http://127.0.0.1:5000/memory"


class _WindowApi:
    def close_nico(self):
        # O botao "x" do HUD só esconde a janela - não encerra o processo.
        # Nico é um assistente que deve continuar ouvindo em segundo plano
        # mesmo com o HUD fechado; destruir a janela aqui encerraria
        # webview.start() e, com isso, o processo inteiro (voz, lembretes,
        # monitor de segurança) - exatamente o bug relatado pelo usuário
        # ("fechei a aba e ele parou de responder à chamada").
        if _window is not None:
            _window.hide()

    def open_memory(self):
        webbrowser.open(_memory_url)


def show_desktop_window():
    if _window is not None:
        _window.show()


def hide_desktop_window():
    if _window is not None:
        _window.hide()


def _wait_for_server(host, port, timeout=10):
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with socket.create_connection((host, port), timeout=0.5):
                return True
        except OSError:
            time.sleep(0.2)
    return False


def open_desktop_window(url, host="127.0.0.1", port=5000, hidden=False, on_ready=None):
    global _window, _memory_url
    _memory_url = f"http://{host}:{port}/memory"
    _wait_for_server(host, port)
    screen = webview.screens[0]
    x = max(0, (screen.width - WINDOW_WIDTH) // 2)
    _window = webview.create_window(
        WINDOW_TITLE,
        url,
        width=WINDOW_WIDTH,
        height=WINDOW_HEIGHT,
        x=x,
        y=12,
        background_color=BACKGROUND_COLOR,
        min_size=(460, 210),
        hidden=hidden,
        frameless=True,
        on_top=True,
        easy_drag=True,
        js_api=_WindowApi(),
    )
    webview.start(func=on_ready)
