from dataclasses import dataclass, field
from typing import List, Tuple

import requests

from cloud_llm import ask_cloud_fallback
from config import (
    INCOMPLETE_TRAILING_WORDS,
    MIN_COMMAND_WORDS,
    NOTIFY_TRIGGERS,
    REALTIME_KEYWORDS,
    REMEMBER_RECALL_PREFIXES,
    REMEMBER_TRIGGERS,
    TAVILY_API_KEY,
    TELEGRAM_USER,
)
from database import save_conversation, save_fact
from documents import build_document_prompt, search_documents
from facts import build_facts_prompt, search_facts
from llm import ask_ollama, build_context_prompt, get_current_time
from memory import find_conversation
from notify import send_telegram_message
from reminders import maybe_schedule_reminder
from text_utils import is_incomplete_command, is_realtime_query, normalize_text
from web_search import build_search_prompt, search_web


@dataclass
class CommandResult:
    kind: str  # "ANSWER", "CLARIFY" ou "INCOMPLETE"
    text: str
    candidates: List[Tuple[str, str]] = field(default_factory=list)


def classify_command(command_text):
    normalized = normalize_text(command_text)
    words = normalized.split()

    if any(word in {"time", "hour", "clock"} for word in words):
        return "TIME"

    if any(word in {"hello", "hi", "hey"} for word in words):
        return "GREETING"

    if "how are you" in normalized or "how are you doing" in normalized:
        return "MOOD"

    if "thank you" in normalized:
        return "THANKS"

    if "what can you do" in normalized or "what are you able to do" in normalized:
        return "CAPABILITIES"

    if "who are you" in normalized or "what are you" in normalized:
        return "IDENTITY"

    # "do you remember ...?" is a recall question, not a request to store a
    # new fact - let it fall through to the LLM path (facts search included).
    if not any(normalized.startswith(prefix) for prefix in REMEMBER_RECALL_PREFIXES):
        if any(trigger in normalized for trigger in REMEMBER_TRIGGERS):
            return "REMEMBER"

    if any(trigger in normalized for trigger in NOTIFY_TRIGGERS):
        return "NOTIFY"

    return "LLM"


def handle_command(command_text, conversation_history):
    command_type = classify_command(command_text)

    if command_type == "TIME":
        return CommandResult("ANSWER", f"The time is {get_current_time()}.")

    if command_type == "GREETING":
        return CommandResult("ANSWER", "Hello! How can I help you today?")

    if command_type == "MOOD":
        return CommandResult("ANSWER", "I'm doing well, thanks for asking. How can I help?")

    if command_type == "THANKS":
        return CommandResult("ANSWER", "You're welcome!")

    if command_type == "CAPABILITIES":
        return CommandResult(
            "ANSWER",
            "I can answer questions, tell the time, chat with you, and help with simple local tasks."
        )

    if command_type == "IDENTITY":
        return CommandResult("ANSWER", "I'm Nico, your local voice assistant.")

    if command_type == "REMEMBER":
        save_fact(command_text)
        reminder_time = maybe_schedule_reminder(command_text)
        if reminder_time:
            return CommandResult(
                "ANSWER", f"Got it, I'll remember that - and I'll remind you on {reminder_time}."
            )
        return CommandResult("ANSWER", "Got it, I'll remember that.")

    if command_type == "NOTIFY":
        return CommandResult("ANSWER", _send_phone_notification(command_text))

    # command_type == "LLM"
    if is_incomplete_command(command_text, MIN_COMMAND_WORDS, INCOMPLETE_TRAILING_WORDS):
        return CommandResult("INCOMPLETE", "Could you finish that thought?")

    memory_result = find_conversation(command_text)

    if memory_result.status == "hit":
        print("Cache Hit - Resposta do BdD")
        return CommandResult("ANSWER", memory_result.answer)

    if memory_result.status == "ambiguous":
        print("Cache Ambiguous - pedindo esclarecimento")
        return CommandResult(
            "CLARIFY",
            "I found more than one similar memory. Could you say it again, a bit more specifically?",
            candidates=memory_result.candidates,
        )

    print("Cache Miss")
    answer = _get_llm_answer(command_text, conversation_history)
    conversation_history.append((command_text, answer))
    save_conversation(command_text, answer)
    return CommandResult("ANSWER", answer)


def _send_phone_notification(command_text):
    normalized = normalize_text(command_text)
    message = command_text
    for trigger in NOTIFY_TRIGGERS:
        if trigger in normalized:
            index = normalized.find(trigger)
            rest = command_text[index + len(trigger):].strip(" ,:.-")
            if rest:
                message = rest
            else:
                message = "Nico here - you asked me to send a message."
            break

    try:
        send_telegram_message(f"Nico: {message}")
        return "Sent! Check your Telegram."
    except Exception as error:
        print("Telegram notification failed:", error)
        return "I couldn't send the message right now."


def _get_llm_answer(command_text, conversation_history):
    """Decide entre fatos lembrados, documentos locais, modelo local, busca
    na web + nuvem, e nuvem como reforço.

    Ordem de tentativa:
    1. Procura entre os fatos que o usuário pediu para o Nico lembrar (ver
       comando REMEMBER em handle_command). É a fonte mais pessoal e
       específica, então é a primeira tentativa.
    2. Procura nos documentos de pesquisa salvos localmente (pasta do
       Google Drive sincronizada, ver DOCUMENTS_FOLDER/NOTES_FOLDER). É
       grátis e instantâneo, só é usado se achar algo realmente relevante.
    3. Se a pergunta parece precisar de informação atual (REALTIME_KEYWORDS)
       e há uma chave do Tavily configurada, busca na web e pede para a
       nuvem (Groq -> Gemini) responder usando os resultados.
    4. Caso contrário (ou se a busca falhar), usa o Ollama local.
    5. Se o Ollama local não responder (offline, travado, etc.), tenta a
       nuvem (Groq -> Gemini) como reforço de confiabilidade.
    6. Se absolutamente tudo falhar, devolve uma resposta de erro amigável
       em vez de deixar a exceção derrubar o assistente.
    """
    fact_matches = search_facts(command_text)
    if fact_matches:
        try:
            print(f"Found {len(fact_matches)} relevant remembered fact(s)")
            prompt = build_facts_prompt(command_text, fact_matches)
            return ask_ollama(prompt)
        except requests.RequestException as error:
            print("Local model unavailable for facts answer, falling back:", error)

    document_matches = search_documents(command_text)
    if document_matches:
        try:
            print(f"Found {len(document_matches)} relevant note(s) in saved research documents")
            prompt = build_document_prompt(command_text, document_matches)
            return ask_ollama(prompt)
        except requests.RequestException as error:
            print("Local model unavailable for document answer, falling back:", error)

    if TAVILY_API_KEY and is_realtime_query(command_text, REALTIME_KEYWORDS):
        try:
            print("Realtime query detected - searching the web")
            results = search_web(command_text)
            prompt = build_search_prompt(command_text, results)
            return ask_cloud_fallback(prompt)
        except Exception as error:
            print("Web search fallback failed, trying the local model instead:", error)

    try:
        print("Asking local Ollama model")
        return ask_ollama(build_context_prompt(command_text, conversation_history))
    except requests.RequestException as error:
        print("Local Ollama unavailable, trying cloud fallback:", error)
        try:
            return ask_cloud_fallback(build_context_prompt(command_text, conversation_history))
        except Exception as cloud_error:
            print("Cloud fallback also failed:", cloud_error)
            if TELEGRAM_USER:
                try:
                    send_telegram_message(
                        "Nico is down: both the local Ollama model and the cloud "
                        "backup (Groq/Gemini) failed to answer."
                    )
                except Exception as notify_error:
                    print("Also failed to send the down-alert notification:", notify_error)
            return "I can't reach my local model or the cloud backup right now. Please try again in a moment."


def resolve_clarification(reply_text, candidates, command_text, conversation_history):
    reply_tokens = normalize_text(reply_text).split()

    if candidates:
        if any(word in reply_tokens for word in ("first", "one", "1")):
            return candidates[0][1]
        if len(candidates) > 1 and any(word in reply_tokens for word in ("second", "two", "2")):
            return candidates[1][1]

        best_answer = None
        best_overlap = 0
        for saved_question, saved_answer in candidates:
            overlap = len(set(reply_tokens) & set(normalize_text(saved_question).split()))
            if overlap > best_overlap:
                best_overlap = overlap
                best_answer = saved_answer
        if best_answer is not None:
            return best_answer

    answer = _get_llm_answer(command_text, conversation_history)
    conversation_history.append((command_text, answer))
    save_conversation(command_text, answer)
    return answer
