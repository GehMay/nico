import threading

# Histórico de conversas da sessão atual (RAM), compartilhado entre a GUI,
# o loop de voz e o servidor web.
conversation_history = []

_lock = threading.Lock()
_status = "Nico está iniciando..."


def get_status():
    with _lock:
        return _status


def set_status(message):
    global _status
    with _lock:
        _status = message
