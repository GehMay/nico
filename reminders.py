import datetime
import re
import time

from dateparser.search import search_dates

from config import REMINDER_DEFAULT_HOUR, REMINDER_TIMEZONE
from database import fetch_due_reminders, mark_reminder_notified, save_reminder
from notify import send_telegram_message
from tts import speak

_SEARCH_SETTINGS = {
    "TIMEZONE": REMINDER_TIMEZONE,
    "RETURN_AS_TIMEZONE_AWARE": True,
    "PREFER_DATES_FROM": "future",
}

_EXPLICIT_TIME_MARKERS = (
    "am", "pm", "a.m", "p.m", "noon", "midnight", ":",
    "morning", "afternoon", "evening", "night",
)
_RELATIVE_DURATION_RE = re.compile(r"\bin\s+\d+\s*(minute|minutes|hour|hours|day|days|week|weeks)\b")


def parse_due_date(text):
    """Tenta achar uma data/hora dentro do texto. Retorna um datetime UTC
    (timezone-aware) no futuro, ou None se não achar nada confiável.

    dateparser é bom, mas tem armadilhas conhecidas com frases sem hora
    explícita ("at 5" sem am/pm, ou datas "soltas" sem contexto) - por
    isso as regras de segurança abaixo: se não tiver certeza da hora, usa
    um horário padrão; se o resultado cair no passado, tenta o dia
    seguinte; se mesmo assim ficar estranho, desiste (não agenda nada em
    vez de avisar na hora errada).
    """
    try:
        results = search_dates(text, languages=["en"], settings=_SEARCH_SETTINGS)
    except Exception:
        return None

    if not results:
        return None

    fragment, parsed = results[-1]
    fragment_lower = fragment.lower()

    is_relative_duration = bool(_RELATIVE_DURATION_RE.search(fragment_lower))
    has_explicit_time = is_relative_duration or any(
        marker in fragment_lower for marker in _EXPLICIT_TIME_MARKERS
    )

    if not has_explicit_time:
        parsed = parsed.replace(hour=REMINDER_DEFAULT_HOUR, minute=0, second=0, microsecond=0)

    due_utc = parsed.astimezone(datetime.timezone.utc)
    now_utc = datetime.datetime.now(datetime.timezone.utc)

    if due_utc <= now_utc:
        # A hora do dia já passou hoje (ex.: "at 5pm" dito às 18h) - assume
        # o dia seguinte na mesma hora, em vez de ficar no passado.
        due_utc += datetime.timedelta(days=1)

    if due_utc <= now_utc:
        # Ainda no passado (ou a interpretação claramente deu errado) -
        # mais seguro não agendar nada do que avisar na hora errada.
        return None

    return due_utc


def maybe_schedule_reminder(command_text):
    """Se o texto tiver uma data/hora reconhecível, agenda um lembrete e
    retorna uma descrição amigável do horário; senão retorna None.
    """
    due_utc = parse_due_date(command_text)
    if due_utc is None:
        return None

    save_reminder(command_text, due_utc.isoformat())

    local_time = due_utc.astimezone()
    return local_time.strftime("%A, %b %d at %I:%M %p").lstrip("0").replace(" 0", " ")


def check_due_reminders(set_status):
    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()

    for reminder_id, reminder_text in fetch_due_reminders(now_iso):
        message = f"Reminder: {reminder_text}"
        print("Reminder due:", message)

        try:
            send_telegram_message(message)
        except Exception as error:
            print("Failed to send reminder via Telegram:", error)

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
