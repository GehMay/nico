import threading

# Histórico de conversas da sessão atual (RAM), compartilhado entre a GUI,
# o loop de voz e o servidor web.
conversation_history = []

_lock = threading.Lock()
_status = "Nico está iniciando..."

# Botão de "pausar o microfone" no HUD - pra testar o Nico em lugar público
# sem ele ficar ouvindo o ambiente. Começa ligado (True = escutando normal).
_mic_enabled = True
_pending_research = None


def get_status():
    with _lock:
        return _status


def set_status(message):
    global _status
    with _lock:
        _status = message


def is_mic_enabled():
    with _lock:
        return _mic_enabled


def set_mic_enabled(enabled):
    global _mic_enabled
    with _lock:
        _mic_enabled = enabled


def get_pending_research():
    with _lock:
        return dict(_pending_research) if _pending_research else None


def set_pending_research(request):
    global _pending_research
    with _lock:
        _pending_research = dict(request) if request else None
