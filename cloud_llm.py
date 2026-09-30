import requests

from config import (
    CLOUD_TIMEOUT,
    GEMINI_API_KEY,
    GEMINI_MODEL,
    GROQ_API_KEY,
    GROQ_MODEL,
)

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
GEMINI_URL = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent"

SYSTEM_PROMPT = (
    "You are Nico, a friendly local voice assistant. Reply in short, natural "
    "spoken English, under three sentences unless the user clearly asked for detail."
)


def ask_groq(prompt):
    if not GROQ_API_KEY:
        raise RuntimeError("GROQ_API_KEY is not configured")

    response = requests.post(
        GROQ_URL,
        headers={"Authorization": f"Bearer {GROQ_API_KEY}"},
        json={
            "model": GROQ_MODEL,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.4,
        },
        timeout=CLOUD_TIMEOUT,
    )
    response.raise_for_status()
    data = response.json()
    return data["choices"][0]["message"]["content"].strip()


def ask_gemini(prompt):
    if not GEMINI_API_KEY:
        raise RuntimeError("GEMINI_API_KEY is not configured")

    response = requests.post(
        GEMINI_URL,
        params={"key": GEMINI_API_KEY},
        json={
            "system_instruction": {"parts": [{"text": SYSTEM_PROMPT}]},
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.4},
        },
        timeout=CLOUD_TIMEOUT,
    )
    response.raise_for_status()
    data = response.json()
    return data["candidates"][0]["content"]["parts"][0]["text"].strip()


def ask_cloud_fallback(prompt):
    """Tenta Groq primeiro; se falhar (sem chave, cota estourada, erro de
    rede etc.), tenta Gemini. Se os dois falharem, levanta a última exceção
    para quem chamou decidir o que fazer.
    """
    errors = []

    for provider_name, ask_fn in (("Groq", ask_groq), ("Gemini", ask_gemini)):
        try:
            return ask_fn(prompt)
        except Exception as error:
            print(f"{provider_name} fallback failed:", error)
            errors.append(f"{provider_name}: {error}")

    raise RuntimeError("All cloud fallbacks failed - " + " | ".join(errors))
