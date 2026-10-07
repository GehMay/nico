import datetime
import re
import time

from dateparser.search import search_dates

from config import REMINDER_DEFAULT_HOUR, REMINDER_TIMEZONE
from database import fetch_due_reminders, fetch_reminders_between, mark_reminder_notified, save_reminder
from tts import speak

_SEARCH_SETTINGS = {
    "TIMEZONE": REMINDER_TIMEZONE,
    "RETURN_AS_TIMEZONE_AWARE": True,
    "PREFER_DATES_FROM": "future",
}

_RELATIVE_DURATION_RE = re.compile(
    r"\bem\s+\d+\s*(minuto|minutos|hora|horas|dia|dias|semana|semanas)\b"
)

# dateparser (locale "pt") lê mal uma hora numérica junto de um dia da
# semana ou "amanhã" - ex.: "sexta-feira às 14h" dá dia 14 do mês (ignora
# a sexta-feira e trata "14h" como dia, não hora); "amanhã às 9h" erra o
# dia e a hora. Por isso a hora explícita (ex.: "às 14h", "as 9 horas") é
# extraída e removida ANTES de passar o texto pro dateparser - ele só
# recebe a parte da data ("sexta-feira", "amanhã"), que resolve bem
# sozinho, e a hora extraída manualmente é aplicada depois.
_TIME_PHRASE_RE = re.compile(
    r"\b(?:as|às)\s+(\d{1,2})\s*(?:[:h]\s*(\d{2})?|horas?)"
    r"(?:\s*(da manha|de manha|da tarde|de tarde|da noite|de noite))?",
    re.IGNORECASE,
)
_PM_PERIODS = ("da tarde", "de tarde", "da noite", "de noite")
_AM_PERIODS = ("da manha", "de manha")


def _extract_explicit_time(text):
    """Acha uma hora explícita tipo "às 14h"/"as 9 horas" no texto, e
    devolve (texto_sem_essa_parte, hora, minuto). Se não achar nada,
    devolve (texto original, None, None).
    """
    match = _TIME_PHRASE_RE.search(text)
    if not match:
        return text, None, None

    hour = int(match.group(1))
    minute = int(match.group(2)) if match.group(2) else 0
    period = (match.group(3) or "").lower()

    if period in _PM_PERIODS and hour < 12:
        hour += 12
    elif period in _AM_PERIODS and hour == 12:
        hour = 0

    cleaned = (text[:match.start()] + text[match.end():]).strip()
    return cleaned, hour, minute


def parse_due_date(text):
    """Tenta achar uma data/hora dentro do texto. Retorna um datetime UTC
    (timezone-aware) no futuro, ou None se não achar nada confiável.

    dateparser é bom pra achar a data (hoje, amanhã, sexta-feira...), mas
    tem armadilhas conhecidas com a hora - por isso ela é extraída à parte
    (ver _extract_explicit_time) em vez de confiar no dateparser pra tudo.
    Se não tiver uma hora explícita, usa um horário padrão; se o resultado
    cair no passado, tenta o dia seguinte; se mesmo assim ficar estranho,
    desiste (não agenda nada em vez de avisar na hora errada).
    """
    cleaned_text, explicit_hour, explicit_minute = _extract_explicit_time(text)

    try:
        results = search_dates(cleaned_text, languages=["pt"], settings=_SEARCH_SETTINGS)
    except Exception:
        return None

    if not results:
        return None

    fragment, parsed = results[-1]
    fragment_lower = fragment.lower()

    if explicit_hour is not None:
        parsed = parsed.replace(hour=explicit_hour, minute=explicit_minute, second=0, microsecond=0)
    elif _RELATIVE_DURATION_RE.search(fragment_lower):
        pass  # dateparser já calculou a hora certa a partir de "em N horas/dias" etc.
    else:
        parsed = parsed.replace(hour=REMINDER_DEFAULT_HOUR, minute=0, second=0, microsecond=0)

    due_utc = parsed.astimezone(datetime.timezone.utc)
    now_utc = datetime.datetime.now(datetime.timezone.utc)

    if due_utc <= now_utc:
        # A hora do dia já passou hoje (ex.: "às 17h" dito às 18h) - assume
        # o dia seguinte na mesma hora, em vez de ficar no passado.
        due_utc += datetime.timedelta(days=1)

    if due_utc <= now_utc:
        # Ainda no passado (ou a interpretação claramente deu errado) -
        # mais seguro não agendar nada do que avisar na hora errada.
        return None

    return due_utc


_WEEKDAYS_PT = (
    "segunda-feira", "terça-feira", "quarta-feira", "quinta-feira",
    "sexta-feira", "sábado", "domingo",
)
_MONTHS_PT = (
    "janeiro", "fevereiro", "março", "abril", "maio", "junho",
    "julho", "agosto", "setembro", "outubro", "novembro", "dezembro",
)


def _format_local_pt(local_time):
    """Formata a data/hora em português, sem depender do locale do sistema
    (que no Windows deste projeto não está em pt-BR e deixaria o nome do
    dia/mês em inglês mesmo com o texto todo traduzido).
    """
    weekday = _WEEKDAYS_PT[local_time.weekday()]
    month = _MONTHS_PT[local_time.month - 1]
    return f"{weekday}, {local_time.day} de {month}, às {local_time.strftime('%H:%M')}"


def maybe_schedule_reminder(command_text):
    """Se o texto tiver uma data/hora reconhecível, agenda um lembrete e
    retorna uma descrição amigável do horário; senão retorna None.
    """
    due_utc = parse_due_date(command_text)
    if due_utc is None:
        return None

    save_reminder(command_text, due_utc.isoformat())

    local_time = due_utc.astimezone()
    return _format_local_pt(local_time)


# "timer de 10 minutos", "cronometro de 30 segundos" - reaproveita o
# "em N horas/minutos" que parse_due_date já sabe interpretar corretamente
# (ver _RELATIVE_DURATION_RE acima), em vez de duplicar essa lógica.
_TIMER_DURATION_RE = re.compile(
    r"(\d+)\s*(segundos?|minutos?|horas?)\b", re.IGNORECASE
)


def schedule_timer(command_text):
    """Agenda um timer simples a partir de uma duração falada (ex.: "timer
    de 10 minutos"). Retorna a duração formatada ("10 minutos") se
    conseguiu agendar, ou None se não achou uma duração reconhecível.
    """
    match = _TIMER_DURATION_RE.search(command_text.lower())
    if not match:
        return None

    quantity, unit = match.group(1), match.group(2)
    due_utc = parse_due_date(f"em {quantity} {unit}")
    if due_utc is None:
        return None

    save_reminder(f"o timer de {quantity} {unit} terminou", due_utc.isoformat())
    return f"{quantity} {unit}"


def get_today_agenda():
    """Devolve uma lista de strings "HH:MM - texto" com os lembretes de
    hoje (passados ou futuros), ou None se não houver nenhum.
    """
    now_local = datetime.datetime.now().astimezone()
    start_local = now_local.replace(hour=0, minute=0, second=0, microsecond=0)
    end_local = start_local + datetime.timedelta(days=1)

    start_utc = start_local.astimezone(datetime.timezone.utc).isoformat()
    end_utc = end_local.astimezone(datetime.timezone.utc).isoformat()

    rows = fetch_reminders_between(start_utc, end_utc)
    if not rows:
        return None

    items = []
    for reminder_text, due_at in rows:
        due_local = datetime.datetime.fromisoformat(due_at).astimezone()
        items.append(f"{due_local.strftime('%H:%M')} - {reminder_text}")
    return items


def check_due_reminders(set_status):
    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()

    for reminder_id, reminder_text in fetch_due_reminders(now_iso):
        message = f"Lembrete: {reminder_text}"
        print("Reminder due:", message)

        try:
            speak(message, set_status)
        except Exception as error:
            print("Failed to speak reminder out loud:", error)

        mark_reminder_notified(reminder_id)


def reminder_loop(set_status, check_interval_seconds):
    while True:
        try:
            check_due_reminders(set_status)
        except Exception as error:
            print("Unexpected error checking reminders:", error)
        time.sleep(check_interval_seconds)
