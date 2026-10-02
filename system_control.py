import ctypes
import datetime
import difflib
import os
import subprocess
import webbrowser
from urllib.parse import quote

import psutil
from PIL import ImageGrab

from config import APP_SHORTCUTS, SCREENSHOT_FOLDER, SITE_SHORTCUTS

# Palavras de preenchimento que aparecem em pedidos falados ("abra o MEU
# instagram") mas não fazem parte do nome do app/site em si.
_FILLER_WORDS = {"o", "a", "os", "as", "meu", "minha", "meus", "minhas", "favor"}

# Cutoff de similaridade (0 a 1) para aceitar um nome parecido mas não
# idêntico (ex.: "instragram" reconhecido em vez de "instagram") como o
# app/site certo, em vez de cair direto numa busca no Google.
_FUZZY_MATCH_CUTOFF = 0.75


def _clean_target_name(name):
    tokens = [token for token in name.split() if token not in _FILLER_WORDS]
    return " ".join(tokens) if tokens else name


def _resolve_known_name(name):
    """Acha o nome mais parecido em APP_SHORTCUTS/SITE_SHORTCUTS, tolerando
    pequenos erros de reconhecimento de voz. Retorna o nome corrigido, ou o
    nome original se nada parecido o suficiente for encontrado.
    """
    known_names = list(APP_SHORTCUTS) + list(SITE_SHORTCUTS)
    matches = difflib.get_close_matches(name, known_names, n=1, cutoff=_FUZZY_MATCH_CUTOFF)
    return matches[0] if matches else name

# Códigos de tecla virtual do Windows para as teclas de mídia de volume.
# Não precisa de nenhuma biblioteca extra - é só a API do Windows via ctypes.
_VK_VOLUME_MUTE = 0xAD
_VK_VOLUME_DOWN = 0xAE
_VK_VOLUME_UP = 0xAF
_KEYEVENTF_KEYUP = 0x0002


def _press_media_key(vk_code):
    ctypes.windll.user32.keybd_event(vk_code, 0, 0, 0)
    ctypes.windll.user32.keybd_event(vk_code, 0, _KEYEVENTF_KEYUP, 0)


def volume_up():
    _press_media_key(_VK_VOLUME_UP)


def volume_down():
    _press_media_key(_VK_VOLUME_DOWN)


def volume_mute():
    _press_media_key(_VK_VOLUME_MUTE)


def open_target(spoken_name):
    """Abre um app conhecido, um site conhecido, ou cai numa busca no
    Google com o nome falado. Retorna uma frase descrevendo o que fez.
    """
    name = _clean_target_name(spoken_name.strip().lower())
    name = _resolve_known_name(name)

    if name in APP_SHORTCUTS:
        command = APP_SHORTCUTS[name]
        try:
            if command.endswith(":"):
                os.startfile(command)
            else:
                subprocess.Popen(command, shell=True)
            return f"Abrindo {name}."
        except OSError as error:
            return f"Não consegui abrir {name}: {error}"

    if name in SITE_SHORTCUTS:
        url = SITE_SHORTCUTS[name]
        if url is None:
            webbrowser.open("about:blank")
        else:
            webbrowser.open(url)
        return f"Abrindo {name}."

    # Não conhecido - tenta abrir como site direto, senão busca no Google.
    if "." in name and " " not in name:
        webbrowser.open(f"https://{name}")
        return f"Abrindo {name}."

    webbrowser.open(f"https://www.google.com/search?q={quote(name)}")
    return f"Não reconheci {name}, então pesquisei no Google."


def take_screenshot():
    os.makedirs(SCREENSHOT_FOLDER, exist_ok=True)
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    path = os.path.join(SCREENSHOT_FOLDER, f"screenshot_{timestamp}.png")

    image = ImageGrab.grab()
    image.save(path)
    return path


def get_battery_status():
    battery = psutil.sensors_battery()
    if battery is None:
        return "Este dispositivo não informa bateria - provavelmente é um desktop."

    percent = round(battery.percent)
    if battery.power_plugged:
        return f"A bateria está em {percent} por cento e carregando."
    return f"A bateria está em {percent} por cento, sem carregar."
