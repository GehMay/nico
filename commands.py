from dataclasses import dataclass, field
from typing import List, Tuple

import requests

from cloud_llm import ask_cloud_fallback
from config import (
    BATTERY_TRIGGERS,
    INCOMPLETE_TRAILING_WORDS,
    MIN_COMMAND_WORDS,
    OPEN_PREFIXES,
    REALTIME_KEYWORDS,
    REMEMBER_RECALL_PREFIXES,
    REMEMBER_TRIGGERS,
    SCREENSHOT_TRIGGERS,
    TAVILY_API_KEY,
    VOLUME_DOWN_WORDS,
    VOLUME_KEYWORDS,
    VOLUME_MUTE_TRIGGERS,
    VOLUME_MUTE_WORDS,
    VOLUME_UP_WORDS,
    WEATHER_TRIGGERS,
)
from database import save_conversation, save_fact
from documents import build_document_prompt, search_documents
from facts import build_facts_prompt, search_facts
from llm import ask_ollama, build_context_prompt, get_current_time
from memory import find_conversation
from reminders import maybe_schedule_reminder
from system_control import get_battery_status, open_target, take_screenshot, volume_down, volume_mute, volume_up
from text_utils import is_incomplete_command, is_realtime_query, normalize_text, strip_request_wrapper
from weather import get_weather_report
from web_search import build_search_prompt, search_web


@dataclass
class CommandResult:
    kind: str  # "ANSWER", "CLARIFY" ou "INCOMPLETE"
    text: str
    candidates: List[Tuple[str, str]] = field(default_factory=list)


def classify_command(command_text):
    normalized = normalize_text(command_text)
    words = normalized.split()

    if any(word in {"hora", "horas", "relogio"} for word in words):
        return "TIME"

    if any(word in {"ola", "oi", "opa", "alo"} for word in words):
        return "GREETING"

    if any(phrase in normalized for phrase in ("como voce esta", "como vai", "tudo bem")):
        return "MOOD"

    if "obrigad" in normalized or "valeu" in normalized:
        return "THANKS"

    if "o que voce pode fazer" in normalized or "o que voce sabe fazer" in normalized:
        return "CAPABILITIES"

    if "quem e voce" in normalized or "o que e voce" in normalized:
        return "IDENTITY"

    # "você lembra...?" é uma pergunta de recordação, não um pedido pra
    # guardar um fato novo - deixa cair no caminho do LLM (que já busca
    # nos fatos salvos).
    if not any(normalized.startswith(prefix) for prefix in REMEMBER_RECALL_PREFIXES):
        if any(trigger in normalized for trigger in REMEMBER_TRIGGERS):
            return "REMEMBER"

    if normalized.startswith(OPEN_PREFIXES):
        return "OPEN"

    if any(trigger in normalized for trigger in VOLUME_MUTE_TRIGGERS):
        return "VOLUME_MUTE"

    # "volume"/"som" + uma palavra de direção, em qualquer ordem na frase
    # (ex.: "aumenta o volume", "coloca o som mais alto") - todas batem.
    if any(keyword in normalized for keyword in VOLUME_KEYWORDS):
        words_set = set(words)
        if words_set & VOLUME_MUTE_WORDS:
            return "VOLUME_MUTE"
        if words_set & VOLUME_UP_WORDS:
            return "VOLUME_UP"
        if words_set & VOLUME_DOWN_WORDS:
            return "VOLUME_DOWN"

    if any(trigger in normalized for trigger in SCREENSHOT_TRIGGERS):
        return "SCREENSHOT"

    if any(trigger in normalized for trigger in BATTERY_TRIGGERS):
        return "BATTERY"

    if any(trigger in normalized for trigger in WEATHER_TRIGGERS):
        return "WEATHER"

    return "LLM"


def _affirm(message, was_question):
    """Se o pedido veio em formato de pergunta ("você pode abrir X?"),
    prefixa a resposta com uma confirmação cordial ("Claro, abrindo X.").
    Se veio como ordem direta ("abra X"), devolve a mensagem como está,
    sem enrolação - esse é o estilo calmo e um pouco cavalheiresco do Nico.
    """
    if not was_question or not message:
        return message
    return "Claro, " + message[0].lower() + message[1:]


def handle_command(command_text, conversation_history):
    core_text, was_question = strip_request_wrapper(command_text)
    command_type = classify_command(core_text)

    if command_type == "TIME":
        return CommandResult("ANSWER", f"Agora são {get_current_time()}.")

    if command_type == "GREETING":
        return CommandResult("ANSWER", "Olá! Em que posso ajudar hoje?")

    if command_type == "MOOD":
        return CommandResult("ANSWER", "Estou bem, obrigado por perguntar. Como posso ajudar?")

    if command_type == "THANKS":
        return CommandResult("ANSWER", "Por nada! Estou à disposição.")

    if command_type == "CAPABILITIES":
        return CommandResult(
            "ANSWER",
            "Posso responder perguntas, dizer a hora, conversar com você e ajudar com tarefas simples no computador."
        )

    if command_type == "IDENTITY":
        return CommandResult("ANSWER", "Eu sou o Nico, seu assistente de voz pessoal, sempre à sua disposição.")

    if command_type == "REMEMBER":
        save_fact(core_text)
        reminder_time = maybe_schedule_reminder(core_text)
        if reminder_time:
            return CommandResult(
                "ANSWER", f"Entendido, vou me lembrar disso - e aviso você {reminder_time}."
            )
        return CommandResult("ANSWER", "Entendido, vou me lembrar disso.")

    if command_type == "OPEN":
        normalized_core = normalize_text(core_text)
        target = ""
        for prefix in OPEN_PREFIXES:
            if normalized_core.startswith(prefix):
                target = normalized_core[len(prefix):].strip()
                break
        return CommandResult("ANSWER", _affirm(open_target(target), was_question))

    if command_type == "VOLUME_UP":
        volume_up()
        return CommandResult("ANSWER", _affirm("Aumentando o volume.", was_question))

    if command_type == "VOLUME_DOWN":
        volume_down()
        return CommandResult("ANSWER", _affirm("Diminuindo o volume.", was_question))

    if command_type == "VOLUME_MUTE":
        volume_mute()
        return CommandResult("ANSWER", _affirm("Silenciado.", was_question))

    if command_type == "SCREENSHOT":
        try:
            path = take_screenshot()
            return CommandResult("ANSWER", _affirm(f"Captura de tela salva em {path}.", was_question))
        except Exception as error:
            print("Screenshot failed:", error)
            return CommandResult("ANSWER", "Não consegui tirar a captura de tela agora.")

    if command_type == "BATTERY":
        return CommandResult("ANSWER", get_battery_status())

    if command_type == "WEATHER":
        try:
            return CommandResult("ANSWER", get_weather_report())
        except Exception as error:
            print("Weather lookup failed, falling back to web search:", error)
            # cai no caminho normal do LLM (busca na web + nuvem) abaixo

    # command_type == "LLM"
    if is_incomplete_command(core_text, MIN_COMMAND_WORDS, INCOMPLETE_TRAILING_WORDS):
        return CommandResult("INCOMPLETE", "Poderia terminar o que estava dizendo?")

    memory_result = find_conversation(core_text)

    if memory_result.status == "hit":
        print("Cache Hit - Resposta do BdD")
        return CommandResult("ANSWER", memory_result.answer)

    if memory_result.status == "ambiguous":
        print("Cache Ambiguous - pedindo esclarecimento")
        return CommandResult(
            "CLARIFY",
            "Encontrei mais de uma lembrança parecida com isso. Pode repetir de um jeito um pouco mais específico?",
            candidates=memory_result.candidates,
        )

    print("Cache Miss")
    answer = _get_llm_answer(core_text, conversation_history)
    conversation_history.append((core_text, answer))
    save_conversation(core_text, answer)
    return CommandResult("ANSWER", answer)


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
            return "No momento não consigo acessar nem o meu modelo local nem o apoio na nuvem. Poderia tentar de novo em um instante?"


def resolve_clarification(reply_text, candidates, command_text, conversation_history):
    reply_tokens = normalize_text(reply_text).split()

    if candidates:
        if any(word in reply_tokens for word in ("primeira", "primeiro", "um", "1")):
            return candidates[0][1]
        if len(candidates) > 1 and any(word in reply_tokens for word in ("segunda", "segundo", "dois", "2")):
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
