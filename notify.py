import requests

from config import TELEGRAM_API_URL, TELEGRAM_USER


def send_telegram_message(text):
    """Manda uma mensagem de texto pro Telegram do usuário via CallMeBot.
    Levanta uma exceção se TELEGRAM_USER não estiver configurado ou se a
    requisição falhar - quem chama decide como tratar isso.
    """
    if not TELEGRAM_USER:
        raise RuntimeError("TELEGRAM_USER is not configured")

    response = requests.get(
        TELEGRAM_API_URL,
        params={"user": TELEGRAM_USER, "text": text},
        timeout=15,
    )
    response.raise_for_status()

    if "Status: Successful" not in response.text:
        raise RuntimeError(f"CallMeBot did not confirm success: {response.text[:200]}")
