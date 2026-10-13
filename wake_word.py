"""Ativação local do Nico por palavra-chave Vosk ou duas palmas."""
import json
import math
import os
import struct
import time
from functools import lru_cache

import state
from config import (
    CLAP_MAX_INTERVAL_SECONDS,
    CLAP_MIN_CREST_FACTOR,
    CLAP_MIN_INTERVAL_SECONDS,
    CLAP_MIN_PEAK,
    CLAP_MIN_RMS,
    CLAP_MIN_ZERO_CROSSING_RATE,
    WAKE_FRAME_LENGTH,
    WAKE_MODEL_PATH,
    WAKE_SAMPLE_RATE,
    WAKE_WORD_ALIASES,
    WAKE_WORDS,
)
from text_utils import normalize_text

try:
    import pyaudio
    from vosk import KaldiRecognizer, Model, SetLogLevel
    _IMPORT_ERROR = None
except ImportError as error:
    pyaudio = None
    KaldiRecognizer = None
    Model = None
    SetLogLevel = None
    _IMPORT_ERROR = error


def is_available():
    return bool(
        _IMPORT_ERROR is None
        and (
            os.path.isfile(os.path.join(WAKE_MODEL_PATH, "final.mdl"))
            or os.path.isfile(os.path.join(WAKE_MODEL_PATH, "am", "final.mdl"))
        )
    )


@lru_cache(maxsize=1)
def _load_model():
    SetLogLevel(-1)
    return Model(WAKE_MODEL_PATH)


def _contains_wake_word(text):
    for token in normalize_text(text).split():
        if token in WAKE_WORDS or WAKE_WORD_ALIASES.get(token) in WAKE_WORDS:
            return True
    return False


def _is_clap_frame(pcm):
    sample_count = len(pcm) // 2
    if sample_count < 2:
        return False

    samples = struct.unpack_from(f"<{sample_count}h", pcm)
    peak = max(abs(sample) for sample in samples)
    if peak < CLAP_MIN_PEAK:
        return False

    rms = math.sqrt(sum(sample * sample for sample in samples) / sample_count)
    if rms < CLAP_MIN_RMS or peak / rms < CLAP_MIN_CREST_FACTOR:
        return False

    crossings = sum(
        (left < 0 <= right) or (right < 0 <= left)
        for left, right in zip(samples, samples[1:])
    )
    return crossings / sample_count >= CLAP_MIN_ZERO_CROSSING_RATE


class DoubleClapDetector:
    def __init__(self):
        self._first_clap_at = None
        self._last_candidate_at = None

    def process(self, pcm, now=None):
        current_time = time.monotonic() if now is None else now
        if not _is_clap_frame(pcm):
            if (
                self._first_clap_at is not None
                and current_time - self._first_clap_at > CLAP_MAX_INTERVAL_SECONDS
            ):
                self._first_clap_at = None
            return False

        if (
            self._last_candidate_at is not None
            and current_time - self._last_candidate_at < CLAP_MIN_INTERVAL_SECONDS
        ):
            return False

        self._last_candidate_at = current_time
        if self._first_clap_at is None:
            self._first_clap_at = current_time
            return False

        interval = current_time - self._first_clap_at
        if interval <= CLAP_MAX_INTERVAL_SECONDS:
            self._first_clap_at = None
            return True

        self._first_clap_at = current_time
        return False


def listen_for_wake_word(set_status):
    """Espera localmente pela palavra "Nico" ou por duas palmas."""
    set_status("Ouvindo")
    recognizer = KaldiRecognizer(
        _load_model(),
        WAKE_SAMPLE_RATE,
        json.dumps(["nico", "[unk]"]),
    )
    clap_detector = DoubleClapDetector()
    audio = None
    stream = None

    try:
        audio = pyaudio.PyAudio()
        stream = audio.open(
            rate=WAKE_SAMPLE_RATE,
            channels=1,
            format=pyaudio.paInt16,
            input=True,
            frames_per_buffer=WAKE_FRAME_LENGTH,
        )
        while state.is_mic_enabled():
            pcm = stream.read(WAKE_FRAME_LENGTH, exception_on_overflow=False)
            if not state.is_mic_enabled():
                return False
            if clap_detector.process(pcm):
                return True

            if recognizer.AcceptWaveform(pcm):
                text = json.loads(recognizer.Result()).get("text", "")
            else:
                text = json.loads(recognizer.PartialResult()).get("partial", "")
            if _contains_wake_word(text):
                return True
        return False
    finally:
        if stream is not None:
            stream.close()
        if audio is not None:
            audio.terminate()