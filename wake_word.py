"""Detecção de wake-word 100% local via Picovoice Porcupine - opcional.

Hoje, toda vez que o Nico "fica de ouvido" esperando ser chamado, ele manda
um trecho de áudio pro reconhecimento de voz do Google (nuvem) só pra
conferir se a palavra "Nico" foi dita - ou seja, até a escuta passiva usa
rede e a API do Google. Com o Porcupine, essa checagem roda localmente, sem
rede nenhuma, e só quando a wake word é detectada de verdade é que o Nico
liga o reconhecimento por nuvem (pra entender o comando em si).

Para ativar:
  1. Crie uma conta grátis em https://console.picovoice.ai
  2. Copie sua Access Key (painel inicial, "AccessKey").
  3. Em "Porcupine" -> criar uma wake word customizada "Nico", idioma
     Português, plataforma Windows, e baixe o arquivo .ppn gerado.
  4. No .env: PICOVOICE_ACCESS_KEY=<sua chave> e
     PICOVOICE_KEYWORD_PATH=<caminho completo do .ppn baixado>.

Sem isso configurado, o Nico continua detectando a wake word do jeito
original (nuvem/Google) - nada quebra, é só uma melhoria opcional.
"""
import struct

from config import PICOVOICE_ACCESS_KEY, PICOVOICE_KEYWORD_PATH

try:
    import pvporcupine
    import pyaudio
    _IMPORT_ERROR = None
except ImportError as error:
    pvporcupine = None
    pyaudio = None
    _IMPORT_ERROR = error


def is_available():
    return bool(PICOVOICE_ACCESS_KEY and PICOVOICE_KEYWORD_PATH and _IMPORT_ERROR is None)


def listen_for_wake_word(set_status):
    """Bloqueia até ouvir a wake word localmente (sem rede), usando o
    microfone padrão. Levanta uma exceção se o Porcupine não conseguir
    inicializar (ex.: chave inválida, arquivo .ppn não encontrado/errado) -
    quem chama decide como cair de volta pro reconhecimento via nuvem.
    """
    set_status("Ouvindo")

    porcupine = pvporcupine.create(
        access_key=PICOVOICE_ACCESS_KEY,
        keyword_paths=[PICOVOICE_KEYWORD_PATH],
    )
    audio = pyaudio.PyAudio()
    stream = audio.open(
        rate=porcupine.sample_rate,
        channels=1,
        format=pyaudio.paInt16,
        input=True,
        frames_per_buffer=porcupine.frame_length,
    )

    try:
        while True:
            pcm = stream.read(porcupine.frame_length, exception_on_overflow=False)
            pcm = struct.unpack_from("h" * porcupine.frame_length, pcm)
            if porcupine.process(pcm) >= 0:
                return
    finally:
        stream.close()
        audio.terminate()
        porcupine.delete()
