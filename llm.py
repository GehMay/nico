import datetime

import requests

from config import (
    CONTEXT_HISTORY_LIMIT,
    OLLAMA_KEEP_ALIVE,
    OLLAMA_MODEL,
    OLLAMA_NUM_PREDICT,
    OLLAMA_TEMPERATURE,
    OLLAMA_TIMEOUT,
    OLLAMA_URL,
)


def build_context_prompt(command_text, conversation_history):
    if not conversation_history:
        return command_text

    recent = conversation_history[-CONTEXT_HISTORY_LIMIT:]
    context = "\n".join(
        f"Usuário: {user}\nNico: {assistant}"
        for user, assistant in recent
    )
    return f"{context}\nUsuário: {command_text}\nNico:"


def ask_ollama(prompt):
    response = requests.post(
        OLLAMA_URL,
        json={
            "model": OLLAMA_MODEL,
            "prompt": (
                "Você é o Nico, um assistente de voz local. Sua personalidade é "
                "calma, amigável e um pouco cavalheiresca, no estilo do "
                "Jarvis (o assistente do Homem de Ferro): educado, atencioso e "
                "sempre à disposição, sem ser formal ou frio. "
                "Responda em português do Brasil, em frases curtas e naturais. "
                "Mantenha as respostas gentis, simples e em até duas frases. "
                "Nunca se recuse a manter uma conversa normal. "
                "Se o usuário perguntar a hora atual, responda exatamente [TIME]. "
                "Se o usuário disser olá ou perguntar como você está, responda "
                "educadamente e de forma breve. "
                "Exemplos:\n"
                "Usuário: olá\n"
                "Nico: Olá! Em que posso ajudar hoje?\n"
                "Usuário: como você está\n"
                "Nico: Estou bem, obrigado por perguntar. Como posso ajudar?\n"
                "Usuário: que horas são\n"
                "Nico: [TIME]\n"
                f"Usuário: {prompt}\n"
                "Nico:"
            ),
            "stream": False,
            "keep_alive": OLLAMA_KEEP_ALIVE,
            "options": {
                "temperature": OLLAMA_TEMPERATURE,
                "num_predict": OLLAMA_NUM_PREDICT,
            }
        },
        timeout=OLLAMA_TIMEOUT,
    )
    response.raise_for_status()
    return response.json()["response"]


def get_current_time():
    current_time = datetime.datetime.now()
    return current_time.strftime("%H:%M")
