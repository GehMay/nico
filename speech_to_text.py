"""Transcrição local de comandos via Whisper (faster-whisper), no lugar da
transcrição por nuvem (Google) usada antes. A vantagem real, testada antes
de integrar: Whisper entende nomes/palavras em inglês misturados numa frase
em português na mesma passada ("abra o spotify e toque minha playlist do
youtube" saiu perfeito), em vez de precisar de duas chamadas como o
fallback pt-BR/en-US que existia antes. Se não estiver instalado/disponível,
`is_available()` devolve False e `voice.py` volta a usar o Google como
antes - este módulo é aditivo, não obrigatório.
"""
import os

os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")

from functools import lru_cache

from config import (
    WHISPER_COMPUTE_TYPE,
    WHISPER_DEVICE,
    WHISPER_LANGUAGE,
    WHISPER_MODEL_SIZE,
)

try:
    import numpy as np
    from faster_whisper import WhisperModel
    _IMPORT_ERROR = None
except ImportError as error:
    np = None
    WhisperModel = None
    _IMPORT_ERROR = error


def is_available():
    return _IMPORT_ERROR is None


@lru_cache(maxsize=1)
def _load_model():
    return WhisperModel(WHISPER_MODEL_SIZE, device=WHISPER_DEVICE, compute_type=WHISPER_COMPUTE_TYPE)


def preload():
    """Carrega o modelo antecipadamente (chamado em background na
    inicialização do Nico) - sem isso, a primeira transcrição real pagaria
    o custo de carregar o modelo (alguns segundos a mais de um minuto, na
    primeira vez que precisa baixá-lo) no meio do primeiro comando real do
    usuário.
    """
    if not is_available():
        return
    try:
        _load_model()
    except Exception as error:
        print("Falha ao pré-carregar o modelo Whisper:", error)


def transcribe_pcm16k(pcm16k_bytes):
    """pcm16k_bytes: áudio PCM 16-bit mono a 16kHz. Devolve o texto
    transcrito (string vazia se não reconhecer nada, ou se a transcrição
    falhar por qualquer motivo - o chamador trata isso como "não entendi",
    igual ao comportamento antigo com o Google).
    """
    try:
        audio_array = np.frombuffer(pcm16k_bytes, dtype=np.int16).astype(np.float32) / 32768.0
        segments, _info = _load_model().transcribe(audio_array, language=WHISPER_LANGUAGE)
        return " ".join(segment.text for segment in segments).strip()
    except Exception as error:
        print("Falha na transcrição local via Whisper:", error)
        return ""
