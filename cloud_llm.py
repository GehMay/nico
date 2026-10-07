import requests

from config import (
    CLOUD_TIMEOUT,
    GEMINI_API_KEY,
    GEMINI_MODEL,
    GROQ_API_KEY,
    GROQ_MODEL,
)
from personality import NICO_PERSONALITY_PROMPT

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
GEMINI_URL = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent"

SYSTEM_PROMPT = (
    NICO_PERSONALITY_PROMPT
    + " Para respostas destinadas à fala, prefira poucas frases; desenvolva "
    "mais quando o usuário pedir detalhes ou quando a situação exigir clareza."
)


def ask_groq(prompt, system_prompt=SYSTEM_PROMPT):
    if not GROQ_API_KEY:
        raise RuntimeError("GROQ_API_KEY is not configured")

    response = requests.post(
        GROQ_URL,
        headers={"Authorization": f"Bearer {GROQ_API_KEY}"},
        json={
            "model": GROQ_MODEL,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.4,
        },
        timeout=CLOUD_TIMEOUT,
    )
    response.raise_for_status()
    data = response.json()
    return data["choices"][0]["message"]["content"].strip()


def ask_gemini(prompt, system_prompt=SYSTEM_PROMPT):
    if not GEMINI_API_KEY:
        raise RuntimeError("GEMINI_API_KEY is not configured")

    response = requests.post(
        GEMINI_URL,
        params={"key": GEMINI_API_KEY},
        json={
            "system_instruction": {"parts": [{"text": system_prompt}]},
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.4},
        },
        timeout=CLOUD_TIMEOUT,
    )
    response.raise_for_status()
    data = response.json()
    return data["candidates"][0]["content"]["parts"][0]["text"].strip()


def ask_cloud_fallback(prompt, system_prompt=SYSTEM_PROMPT):
    """Tenta Groq primeiro; se falhar (sem chave, cota estourada, erro de
    rede etc.), tenta Gemini. Se os dois falharem, levanta a última exceção
    para quem chamou decidir o que fazer.

    `system_prompt` é opcional - por padrão usa a personalidade de voz
    curta do Nico, mas pode ser trocado (ex.: pelo "modo sério" de
    pesquisa, que precisa de respostas bem mais longas e escritas, não
    faladas).
    """
    errors = []

    for provider_name, ask_fn in (("Groq", ask_groq), ("Gemini", ask_gemini)):
        try:
            return ask_fn(prompt, system_prompt=system_prompt)
        except Exception as error:
            print(f"{provider_name} fallback failed:", error)
            errors.append(f"{provider_name}: {error}")

    raise RuntimeError("All cloud fallbacks failed - " + " | ".join(errors))
