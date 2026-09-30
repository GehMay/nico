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
        f"User: {user}\nAssistant: {assistant}"
        for user, assistant in recent
    )
    return f"{context}\nUser: {command_text}\nAssistant:"


def ask_ollama(prompt):
    response = requests.post(
        OLLAMA_URL,
        json={
            "model": OLLAMA_MODEL,
            "prompt": (
                "You are Nico, a friendly local voice assistant. "
                "Reply in short, natural English. "
                "Keep replies warm, simple, and under two sentences. "
                "Do not refuse normal conversation. "
                "If the user asks for the current time, reply exactly [TIME]. "
                "If the user says hello or asks how you are, answer politely and briefly. "
                "Examples:\n"
                "User: hello\n"
                "Assistant: Hello! How can I help you today?\n"
                "User: how are you doing\n"
                "Assistant: I'm doing well, thanks for asking. How can I help?\n"
                "User: what time is it\n"
                "Assistant: [TIME]\n"
                f"User: {prompt}\n"
                "Assistant:"
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
    return current_time.strftime("%I:%M %p")
