import asyncio
import gc
import hashlib
import os
import tempfile

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

import edge_tts
import pygame
import pyttsx3

from config import NEURAL_VOICE, TTS_CACHE_DIR, USE_NEURAL_VOICE, USE_TTS_CACHE, VOICE_INDEX
import state

_mixer_ready = False


def _ensure_mixer():
    global _mixer_ready
    if not _mixer_ready:
        pygame.mixer.init()
        _mixer_ready = True


def _cache_path(text):
    key = hashlib.sha1(f"{NEURAL_VOICE}|{text}".encode("utf-8")).hexdigest()
    return os.path.join(TTS_CACHE_DIR, f"{key}.mp3")


async def _synthesize(text, audio_path):
    communicate = edge_tts.Communicate(text, voice=NEURAL_VOICE)
    await communicate.save(audio_path)


def _play(audio_path):
    _ensure_mixer()
    pygame.mixer.music.load(audio_path)
    pygame.mixer.music.play()
    while pygame.mixer.music.get_busy():
        pygame.time.wait(100)
    pygame.mixer.music.unload()


def _speak_neural(text):
    # Frases repetidas (saudações, avisos de erro, "could you finish that
    # thought?" etc.) são faladas várias vezes ao longo do uso. Guardar o
    # áudio já gerado evita pagar o tempo de rede do edge-tts de novo.
    if USE_TTS_CACHE:
        cached_path = _cache_path(text)
        if os.path.exists(cached_path):
            _play(cached_path)
            return

        os.makedirs(TTS_CACHE_DIR, exist_ok=True)
        try:
            asyncio.run(_synthesize(text, cached_path))
        except Exception:
            if os.path.exists(cached_path):
                os.remove(cached_path)
            raise
        _play(cached_path)
        return

    fd, audio_path = tempfile.mkstemp(suffix=".mp3")
    os.close(fd)
    try:
        asyncio.run(_synthesize(text, audio_path))
        _play(audio_path)
    finally:
        try:
            os.remove(audio_path)
        except OSError:
            pass


def _speak_local(text):
    voice_engine = pyttsx3.init()
    voices = voice_engine.getProperty("voices")
    voice_engine.setProperty("voice", voices[VOICE_INDEX].id)
    voice_engine.say(text)
    voice_engine.runAndWait()
    voice_engine.stop()
    del voice_engine
    gc.collect()


def speak(text, set_status):
    set_status("Falando")
    try:
        if USE_NEURAL_VOICE:
            try:
                _speak_neural(text)
                return
            except Exception as error:
                print("Neural voice unavailable, falling back to local voice:", error)

        _speak_local(text)
    finally:
        set_status("Pensando" if state.is_mic_enabled() else "Pausado")
