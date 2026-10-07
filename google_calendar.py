"""Leitura (somente-leitura) da agenda do Google Calendar via feed iCal.

Não usa a API oficial do Google (que exigiria registrar um app OAuth) - usa
o "endereço secreto no formato iCal" que o próprio Google Calendar oferece:
  1. No Google Calendar, vá em Configurações da sua agenda.
  2. Em "Integrar agenda", copie o "Endereço secreto no formato iCal".
  3. Cole no .env como GOOGLE_CALENDAR_ICS_URL.

Esse link é somente-leitura e secreto - quem tiver ele consegue ver sua
agenda, então é tratado como segredo (só no .env, nunca no código/Git),
igual as chaves de API.
"""
import datetime
import re

import icalendar
import recurring_ical_events
import requests

from config import GOOGLE_CALENDAR_ICS_URL

_REQUEST_TIMEOUT = 15

# Muitos títulos de evento vêm com emoji na frente (ex.: "🎓 Atividades da
# faculdade") - a voz lê isso de um jeito estranho, então é removido antes
# de montar a frase falada.
_EMOJI_RE = re.compile(
    "["
    "\U0001F300-\U0001FAFF"
    "\U00002600-\U000027BF"
    "\U0001F1E6-\U0001F1FF"
    "️"
    "]+",
    flags=re.UNICODE,
)


def _clean_summary(text):
    return _EMOJI_RE.sub("", text).strip()


def get_today_events():
    """Busca os eventos de hoje no Google Calendar. Devolve uma lista de
    strings formatadas ("HH:MM - título" ou "Dia todo - título"), ou lista
    vazia se não houver GOOGLE_CALENDAR_ICS_URL configurado ou se a busca
    falhar (nunca levanta exceção - é uma fonte best-effort).
    """
    if not GOOGLE_CALENDAR_ICS_URL:
        return []

    try:
        response = requests.get(GOOGLE_CALENDAR_ICS_URL, timeout=_REQUEST_TIMEOUT)
        response.raise_for_status()
        calendar = icalendar.Calendar.from_ical(response.text)
    except Exception as error:
        print("Google Calendar fetch failed:", error)
        return []

    now_local = datetime.datetime.now().astimezone()
    start_local = now_local.replace(hour=0, minute=0, second=0, microsecond=0)
    end_local = start_local + datetime.timedelta(days=1)

    try:
        events = recurring_ical_events.of(calendar).between(start_local, end_local)
    except Exception as error:
        print("Google Calendar parsing failed:", error)
        return []

    items = []
    for event in events:
        summary = _clean_summary(str(event.get("SUMMARY", "Evento sem título")))
        dtstart = event["DTSTART"].dt

        if isinstance(dtstart, datetime.datetime):
            time_label = dtstart.astimezone().strftime("%H:%M")
        else:
            time_label = "Dia todo"

        items.append(f"{time_label} - {summary}")

    items.sort(key=lambda item: "99:99" if item.startswith("Dia todo") else item[:5])
    return items
