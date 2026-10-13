"""Reconhecimento de locutor (x-vector do Vosk) - filtra a voz cadastrada do
usuário de outras vozes captadas pelo microfone (TV, vídeo, outra pessoa).

Funciona em cima do mesmo modelo acústico já usado pela wake word
(`wake_word._load_model()`), mais o pacote de identificação de locutor
`vosk-model-spk-0.4`. Precisa de alguns segundos contínuos de fala pra
extrair um embedding confiável - uma palavra isolada não é suficiente e
`_extract_embedding` simplesmente devolve `None` nesse caso, para que o
chamador trate "não deu pra verificar" como "deixa passar" em vez de
rejeitar um comando curto legítimo do usuário.
"""
import json
import math
import os

import pyaudio

from config import (
    ENROLL_VOICE_DURATION_SECONDS,
    SPEAKER_MODEL_PATH,
    SPEAKER_SIMILARITY_THRESHOLD,
    VOICE_PROFILE_PATH,
    WAKE_FRAME_LENGTH,
    WAKE_SAMPLE_RATE,
)
from crypto_utils import decrypt_text, encrypt_text

try:
    from vosk import KaldiRecognizer, SpkModel
    _IMPORT_ERROR = None
except ImportError as error:
    KaldiRecognizer = None
    SpkModel = None
    _IMPORT_ERROR = error

_spk_model = None


def is_available():
    return bool(
        _IMPORT_ERROR is None
        and os.path.isfile(os.path.join(SPEAKER_MODEL_PATH, "final.ext.raw"))
    )


def _load_spk_model():
    global _spk_model
    if _spk_model is None:
        _spk_model = SpkModel(SPEAKER_MODEL_PATH)
    return _spk_model


def _extract_embedding(pcm16k):
    """pcm16k: áudio PCM 16-bit mono a 16kHz. Devolve a lista de floats do
    x-vector, ou None se o áudio for curto demais para gerar um embedding.
    """
    import wake_word  # import tardio - evita ciclo e reusa o modelo já carregado

    recognizer = KaldiRecognizer(wake_word._load_model(), WAKE_SAMPLE_RATE)
    recognizer.SetSpkModel(_load_spk_model())
    recognizer.AcceptWaveform(pcm16k)
    result = json.loads(recognizer.FinalResult())
    return result.get("spk")


def _cosine_similarity(a, b):
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def has_profile():
    return os.path.isfile(VOICE_PROFILE_PATH)


def save_profile(embedding):
    os.makedirs(os.path.dirname(VOICE_PROFILE_PATH), exist_ok=True)
    payload = encrypt_text(json.dumps(embedding))
    with open(VOICE_PROFILE_PATH, "w", encoding="utf-8") as handle:
        handle.write(payload)


def _load_profile():
    if not has_profile():
        return None
    with open(VOICE_PROFILE_PATH, "r", encoding="utf-8") as handle:
        payload = handle.read()
    try:
        return json.loads(decrypt_text(payload))
    except (ValueError, json.JSONDecodeError):
        return None


def matches_profile(pcm16k):
    """True = bate com o perfil cadastrado. False = não bate (provavelmente
    outra voz/TV). None = não deu pra decidir (sem perfil, ou áudio curto
    demais pra extrair um embedding) - o chamador deve tratar como "deixa
    passar", nunca como rejeição.
    """
    profile = _load_profile()
    if profile is None:
        return None

    embedding = _extract_embedding(pcm16k)
    if embedding is None:
        return None

    similarity = _cosine_similarity(embedding, profile)
    return similarity >= SPEAKER_SIMILARITY_THRESHOLD


def _record_raw_pcm(duration_seconds):
    audio = pyaudio.PyAudio()
    stream = audio.open(
        rate=WAKE_SAMPLE_RATE,
        channels=1,
        format=pyaudio.paInt16,
        input=True,
        frames_per_buffer=WAKE_FRAME_LENGTH,
    )
    frames = []
    frames_needed = int(WAKE_SAMPLE_RATE * duration_seconds)
    collected = 0
    try:
        while collected < frames_needed:
            data = stream.read(WAKE_FRAME_LENGTH, exception_on_overflow=False)
            frames.append(data)
            collected += WAKE_FRAME_LENGTH
    finally:
        stream.close()
        audio.terminate()
    return b"".join(frames)


def enroll_from_microphone(set_status, speak_fn):
    speak_fn(
        "Certo, vou gravar sua voz por alguns segundos. Pode falar naturalmente "
        "a partir de agora.",
        set_status,
    )
    set_status("Executando ação")
    pcm = _record_raw_pcm(ENROLL_VOICE_DURATION_SECONDS)
    embedding = _extract_embedding(pcm)
    if embedding is None:
        speak_fn(
            "Não consegui captar áudio suficiente para o seu perfil de voz. "
            "Podemos tentar de novo quando quiser.",
            set_status,
        )
        return
    save_profile(embedding)
    speak_fn(
        "Perfil de voz salvo. A partir de agora, vou tentar ignorar o que vier "
        "de outras vozes, como televisão ou vídeo.",
        set_status,
    )
