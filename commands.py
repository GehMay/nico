import datetime
import os
import re
from dataclasses import dataclass, field
from typing import List, Tuple

import requests

from cloud_llm import ask_cloud_fallback
from config import (
    AGENDA_TRIGGERS,
    BATTERY_TRIGGERS,
    BRIEFING_TRIGGERS,
    CALC_TRIGGERS,
    CREATE_PROJECT_TRIGGERS,
    INCOMPLETE_TRAILING_WORDS,
    MIN_COMMAND_WORDS,
    NO_MEMORY_TRIGGERS,
    OPEN_NORTON_TRIGGERS,
    OPEN_DOCUMENTATION_TRIGGERS,
    OPEN_PREFIXES,
    REALTIME_KEYWORDS,
    REMEMBER_RECALL_PREFIXES,
    REMEMBER_TRIGGERS,
    RESEARCH_TRIGGERS,
    SECURITY_STATUS_TRIGGERS,
    RESEARCH_STORAGE_TRIGGERS,
    RESEARCH_FOLDER,
    SCREENSHOT_TRIGGERS,
    TAVILY_API_KEY,
    TIMER_TRIGGERS,
    UPDATE_DOCUMENT_TRIGGERS,
    VOLUME_DOWN_WORDS,
    VOLUME_KEYWORDS,
    VOLUME_MUTE_TRIGGERS,
    VOLUME_MUTE_WORDS,
    VOLUME_UP_WORDS,
    WEATHER_TRIGGERS,
    YOUTUBE_SEARCH_FILLER_WORDS,
)
from calculator import calculate_spoken, extract_expression
from code_builder import build_project
from database import save_conversation, save_fact
from documents import build_document_prompt, search_documents
from facts import build_facts_prompt, search_facts
from google_calendar import get_today_events
from llm import ask_ollama, build_context_prompt, get_current_time
from memory import find_conversation
from reminders import get_today_agenda, maybe_schedule_reminder, schedule_timer
from research import run_research
from security_monitor import describe_security_status, get_security_status, open_norton
from state import (
    get_pending_document_update,
    get_pending_research,
    set_pending_document_update,
    set_pending_research,
    set_status,
)
from system_control import (
    get_battery_status,
    open_documentation,
    open_target,
    open_work_mode,
    search_youtube,
    take_screenshot,
    volume_down,
    volume_mute,
    volume_up,
)
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

    if any(trigger in normalized for trigger in SECURITY_STATUS_TRIGGERS):
        return "SECURITY_STATUS"

    if any(trigger in normalized for trigger in OPEN_NORTON_TRIGGERS):
        return "OPEN_NORTON"

    if any(trigger in normalized for trigger in BRIEFING_TRIGGERS):
        return "BRIEFING"

    if any(trigger in normalized for trigger in AGENDA_TRIGGERS):
        return "AGENDA"

    # Só vira CALC se der pra montar uma conta de verdade (número +
    # operador) - senão "quanto é a distância até a lua" cairia aqui em
    # vez de ir pro LLM, que sabe responder isso de verdade.
    if any(trigger in normalized for trigger in CALC_TRIGGERS):
        expression = extract_expression(command_text)
        if expression and any(op in expression for op in ("+", "-", "*", "/")):
            return "CALC"

    if any(trigger in normalized for trigger in TIMER_TRIGGERS):
        return "TIMER"

    # "você lembra...?" é uma pergunta de recordação, não um pedido pra
    # guardar um fato novo - deixa cair no caminho do LLM (que já busca
    # nos fatos salvos).
    if not any(normalized.startswith(prefix) for prefix in REMEMBER_RECALL_PREFIXES):
        if any(trigger in normalized for trigger in REMEMBER_TRIGGERS):
            return "REMEMBER"

    if any(trigger in normalized for trigger in RESEARCH_TRIGGERS):
        return "RESEARCH"

    if any(trigger in normalized for trigger in CREATE_PROJECT_TRIGGERS):
        return "CREATE_PROJECT"

    if any(trigger in normalized for trigger in RESEARCH_STORAGE_TRIGGERS):
        return "RESEARCH_STORAGE"

    if any(trigger in normalized for trigger in UPDATE_DOCUMENT_TRIGGERS):
        return "UPDATE_DOCUMENT"

    if any(normalized == trigger for trigger in NO_MEMORY_TRIGGERS):
        return "NO_MEMORY"

    # "modo" em qualquer lugar da frase (ex.: "modo trabalho", "ativar o
    # modo trabalho", "entra no modo estudos") - o nome do espaço é tudo
    # que vem depois da palavra "modo".
    if "modo" in words:
        return "WORK_MODE"

    if any(trigger in normalized for trigger in OPEN_DOCUMENTATION_TRIGGERS):
        return "OPEN_DOCUMENTATION"

    # "youtube" + algo mais além de só o nome do site - vira uma busca no
    # YouTube ("toca X no youtube"), não o atalho genérico de abrir o site.
    # Checado antes de OPEN_PREFIXES, senão "abra um vídeo de X no youtube"
    # bateria ali primeiro (começa com "abra ").
    if "youtube" in words:
        query = _extract_youtube_query(normalized)
        if query:
            return "YOUTUBE_SEARCH"

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

    if command_type == "UPDATE_DOCUMENT":
        return _continue_document_update(_parse_document_update(core_text), was_question)

    if command_type == "RESEARCH":
        return _continue_or_run_research(_parse_research_fields(core_text), was_question)

    if command_type == "CREATE_PROJECT":
        return _create_project(_extract_after_trigger(core_text, CREATE_PROJECT_TRIGGERS))

    pending_research = get_pending_research()
    if pending_research:
        if normalize_text(core_text) in {"cancela pesquisa", "cancelar pesquisa", "cancela", "cancelar"}:
            set_pending_research(None)
            return CommandResult("ANSWER", "Pesquisa cancelada.")
        return _continue_or_run_research(
            _parse_research_fields(core_text, pending_research), was_question
        )

    pending_document_update = get_pending_document_update()
    if pending_document_update:
        if normalize_text(core_text) in {"cancela atualizacao", "cancelar atualizacao", "cancela", "cancelar"}:
            set_pending_document_update(None)
            return CommandResult("ANSWER", "Atualização do documento cancelada.")
        return _continue_document_update(
            _parse_document_update(core_text, pending_document_update, followup=True),
            was_question,
        )

    if command_type == "RESEARCH_STORAGE":
        if RESEARCH_FOLDER == "pesquisas":
            return CommandResult(
                "ANSWER",
                "A pasta do Drive não está configurada. Os relatórios estão sendo salvos localmente em pesquisas.",
            )
        return CommandResult(
            "ANSWER", f"Os relatórios do Modo Pesquisa já são salvos em {RESEARCH_FOLDER}."
        )

    if command_type == "NO_MEMORY":
        return CommandResult(
            "ANSWER",
            "Certo. Pesquisas do Modo Pesquisa não são gravadas na memória de conversas nem nos fatos lembrados.",
        )

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

    if command_type == "SECURITY_STATUS":
        try:
            return CommandResult("ANSWER", describe_security_status(get_security_status()))
        except Exception as error:
            print("Security status unavailable:", error)
            return CommandResult("ANSWER", "Não consegui consultar o estado do Norton e do Firewall agora.")

    if command_type == "OPEN_NORTON":
        try:
            open_norton()
            return CommandResult(
                "ANSWER", "Abrindo o Norton para você verificar a proteção ou iniciar uma verificação."
            )
        except OSError as error:
            print("Could not open Norton:", error)
            return CommandResult("ANSWER", "Não consegui abrir o Norton neste momento.")

    if command_type == "BRIEFING":
        return CommandResult("ANSWER", _morning_briefing())

    if command_type == "AGENDA":
        items = _combined_agenda_items()
        if not items:
            return CommandResult("ANSWER", "Você não tem nada agendado para hoje.")
        return CommandResult("ANSWER", "Hoje você tem: " + "; ".join(items) + ".")

    if command_type == "CALC":
        result = calculate_spoken(core_text)
        if result is None:
            return CommandResult(
                "ANSWER", "Não consegui entender essa conta. Pode repetir com números e uma operação, tipo 'quanto é 23 vezes 7'?"
            )
        return CommandResult("ANSWER", f"O resultado é {result}.")

    if command_type == "TIMER":
        duration = schedule_timer(core_text)
        if not duration:
            return CommandResult(
                "ANSWER", "Não entendi a duração do timer. Pode dizer, por exemplo, 'timer de 10 minutos'?"
            )
        return CommandResult("ANSWER", _affirm(f"Prontinho, aviso você em {duration}.", was_question))

    if command_type == "REMEMBER":
        save_fact(core_text)
        reminder_time = maybe_schedule_reminder(core_text)
        if reminder_time:
            return CommandResult(
                "ANSWER", f"Entendido, vou me lembrar disso - e aviso você {reminder_time}."
            )
        return CommandResult("ANSWER", "Entendido, vou me lembrar disso.")

    if command_type == "OPEN_DOCUMENTATION":
        topic = _extract_after_trigger(core_text, OPEN_DOCUMENTATION_TRIGGERS)
        return CommandResult("ANSWER", _affirm(open_documentation(topic), was_question))

    if command_type == "YOUTUBE_SEARCH":
        query = _extract_youtube_query(normalize_text(core_text))
        return CommandResult("ANSWER", _affirm(search_youtube(query), was_question))

    if command_type == "WORK_MODE":
        words = normalize_text(core_text).split()
        name = " ".join(words[words.index("modo") + 1:])
        return CommandResult("ANSWER", _affirm(open_work_mode(name), was_question))

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
    # Qualquer pedido que não caia em um gatilho específico continua no fluxo
    # geral do LLM. O Nico não deve encerrar em um "comando desconhecido"
    # quando o usuário pedir algo livre, mesmo que a frase não bata em um
    # atalho fixo do sistema; só bloqueamos pedidos incompletos.
    if is_incomplete_command(core_text, MIN_COMMAND_WORDS, INCOMPLETE_TRAILING_WORDS):
        return CommandResult("INCOMPLETE", "Poderia terminar o que estava dizendo?")

    skip_memory = any(trigger in normalize_text(core_text) for trigger in NO_MEMORY_TRIGGERS)
    memory_result = None if skip_memory else find_conversation(core_text)

    if memory_result and memory_result.status == "hit":
        print("Cache Hit - Resposta do BdD")
        return CommandResult("ANSWER", memory_result.answer)

    if memory_result and memory_result.status == "ambiguous":
        print("Cache Ambiguous - pedindo esclarecimento")
        return CommandResult(
            "CLARIFY",
            "Encontrei mais de uma lembrança parecida com isso. Pode repetir de um jeito um pouco mais específico?",
            candidates=memory_result.candidates,
        )

    print("Cache Miss")
    answer = _get_llm_answer(core_text, conversation_history)
    if answer is None or not answer.strip():
        # Falha total (nada respondeu) ou resposta vazia - não é uma resposta
        # de verdade, então não entra no cache de perguntas/respostas.
        return CommandResult(
            "ANSWER",
            "Desculpe, não consegui acessar nem o meu modelo local nem o de nuvem agora. "
            "Pode tentar de novo em um instante?",
        )
    if not skip_memory:
        save_conversation(core_text, answer)
    return CommandResult("ANSWER", answer)


def _extract_youtube_query(normalized_text):
    """Remove palavras de preenchimento (ver config.YOUTUBE_SEARCH_FILLER_WORDS)
    de uma frase já normalizada, deixando só o termo de busca. Devolve ""
    se não sobrar nada (ex.: "abra o youtube" sozinho, sem termo nenhum).
    """
    tokens = [word for word in normalized_text.split() if word not in YOUTUBE_SEARCH_FILLER_WORDS]
    return " ".join(tokens)


def _resolve_document_target(command_text):
    normalized = normalize_text(command_text)
    if "comandos" in normalized:
        return "COMANDOS_NICO.txt"
    if "documentacao" in normalized or "nico" in normalized:
        return "Nico_Documentacao.txt"
    return None


def _parse_document_update(text, existing=None, followup=False):
    update = dict(existing or {"target": None, "content": ""})
    update["target"] = update.get("target") or _resolve_document_target(text)

    content_match = re.search(
        r"\b(?:com|inclua|incluindo|acrescente|adicionando)\b\s*[:,-]?\s*(.+)$|:(.+)$",
        text,
        re.IGNORECASE,
    )
    if content_match:
        update["content"] = next(value for value in content_match.groups() if value).strip()
    elif followup and not update["target"]:
        update["target"] = _resolve_document_target(text)
        update["content"] = ""
    elif followup and update["target"] and not _resolve_document_target(text):
        update["content"] = text.strip()

    return update


def _continue_document_update(update, was_question=False):
    if not update.get("target") or not update.get("content"):
        set_pending_document_update(update)
        if not update.get("target") and not update.get("content"):
            prompt = (
                "Qual arquivo devo atualizar e o que devo incluir? Responda, por exemplo: "
                "documentação: texto a acrescentar."
            )
        elif not update.get("target"):
            prompt = "Qual arquivo devo atualizar: documentação ou comandos?"
        else:
            prompt = "O que devo incluir no documento?"
        return CommandResult("DOCUMENT_UPDATE_CLARIFY", prompt)

    set_pending_document_update(None)
    try:
        path = _append_document_update(update["target"], update["content"])
    except OSError as error:
        print("Document update failed:", error)
        return CommandResult("ANSWER", "Não consegui atualizar o arquivo. Verifique se ele existe e tente novamente.")
    return CommandResult("ANSWER", _affirm(f"Atualizei o documento em {path}.", was_question))


def _append_document_update(target_name, content):
    allowed_targets = {"Nico_Documentacao.txt", "COMANDOS_NICO.txt"}
    if target_name not in allowed_targets or not content.strip():
        raise ValueError("destino ou conteúdo de atualização inválido")
    project_root = os.path.dirname(os.path.abspath(__file__))
    path = os.path.join(project_root, target_name)
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    with open(path, "a", encoding="utf-8") as handle:
        handle.write(f"\n\n--- Atualização ({timestamp}) ---\n{content.strip()}\n")
    return path


def _extract_after_trigger(command_text, triggers):
    """Devolve o que vem depois da frase-gatilho (ex.: depois de "pesquise
    sobre" em "pesquise sobre buracos negros" devolve "buracos negros").
    Devolve "" se nenhum gatilho for encontrado ou não houver nada depois.
    """
    normalized = normalize_text(command_text)
    for trigger in triggers:
        if trigger in normalized:
            index = normalized.find(trigger)
            rest = command_text[index + len(trigger):].strip(" ,:.-")
            if rest:
                return rest
    return ""


def _parse_research_fields(text, existing=None):
    fields = dict(existing or {"topic": "", "wanted": "", "excluded": ""})
    normalized = normalize_text(text)
    payload = text

    for trigger in RESEARCH_TRIGGERS:
        index = normalized.find(trigger)
        if index >= 0:
            payload = text[index + len(trigger):].strip(" ,:.-")
            break

    unlabeled_values = []
    labels = (
        ("topic", ("tema", "topico", "assunto")),
        ("wanted", ("o que eu quero", "o que quero", "quero", "foco")),
        ("excluded", ("o que eu nao quero", "o que nao quero", "nao quero", "excluir", "evitar")),
    )

    for part in (piece.strip().strip("[] ") for piece in payload.split(",")):
        if not part:
            continue

        assigned = False
        for field_name, aliases in labels:
            for separator in (":", "="):
                if separator in part:
                    label, value = part.split(separator, 1)
                    if normalize_text(label.strip()) in aliases:
                        fields[field_name] = value.strip().strip("[] ")
                        assigned = True
                        break
            if assigned:
                break

            normalized_part = normalize_text(part)
            for alias in sorted(aliases, key=len, reverse=True):
                if normalized_part.startswith(alias + " "):
                    fields[field_name] = part[len(alias):].strip(" :[]=\t")
                    assigned = True
                    break
            if assigned:
                break

        if not assigned:
            unlabeled_values.append(part)

    missing_fields = [name for name, value in fields.items() if not value]
    for field_name, value in zip(missing_fields, unlabeled_values):
        fields[field_name] = value.strip().strip("[] ")

    return fields


def _continue_or_run_research(request, was_question=False):
    missing = [name for name, value in request.items() if not value]
    if missing:
        set_pending_research(request)
        questions = {
            "topic": "Qual é o tema da pesquisa?",
            "wanted": "O que você quer que a pesquisa encontre ou priorize?",
            "excluded": "O que você não quer que entre na pesquisa?",
        }
        if len(missing) == 1:
            question = questions[missing[0]]
        else:
            labels = {
                "topic": "o tema",
                "wanted": "o que você quer que eu priorize",
                "excluded": "o que você não quer que entre",
            }
            question = " e ".join(labels[name] for name in missing).capitalize() + "?"
        return CommandResult(
            "RESEARCH_CLARIFY",
            f"Antes de pesquisar, preciso saber {question[0].lower() + question[1:]} "
            "Responda os campos que faltam separados por vírgulas."
        )

    set_pending_research(None)
    answer = _run_research(request["topic"], request["wanted"], request["excluded"])
    return CommandResult("ANSWER", _affirm(answer, was_question))


def _combined_agenda_items():
    """Junta os lembretes do Nico com os eventos de hoje do Google
    Calendar (se configurado - ver google_calendar.py), ordenados por
    horário.
    """
    items = list(get_today_agenda() or [])
    items.extend(get_today_events())
    items.sort(key=lambda item: "99:99" if item.startswith("Dia todo") else item[:5])
    return items


def _morning_briefing():
    parts = []

    try:
        parts.append(get_weather_report())
    except Exception as error:
        print("Weather lookup failed for briefing:", error)

    agenda_items = _combined_agenda_items()
    if agenda_items:
        parts.append("Hoje você tem: " + "; ".join(agenda_items) + ".")
    else:
        parts.append("Você não tem nada agendado para hoje.")

    return "Bom dia! " + " ".join(parts)


def _run_research(topic, wanted, excluded):
    set_status("Pesquisando")
    try:
        path = run_research(topic, wanted, excluded)
        return f"Pesquisa concluída. Salvei o relatório em {path}."
    except Exception as error:
        print("Research failed:", error)
        return "Não consegui concluir a pesquisa agora. Pode tentar de novo em um instante?"
    finally:
        set_status("Pensando")


def _create_project(description):
    if not description:
        return CommandResult(
            "ANSWER", "O que você quer que eu crie? Descreva o site ou projeto."
        )

    set_status("Executando ação")
    try:
        path = build_project(description)
        return CommandResult(
            "ANSWER",
            f"Criei o projeto em {path}. Dê uma olhada antes de usar - "
            "o Kimi gera o código, mas eu não executo nada automaticamente.",
        )
    except RuntimeError as error:
        print("Project generation failed:", error)
        return CommandResult(
            "ANSWER",
            "Não consegui gerar o projeto agora - confirme se a chave do Kimi "
            "está configurada, ou tente de novo em um instante.",
        )
    finally:
        set_status("Pensando")


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

    set_status("Lendo documentos")
    document_matches = search_documents(command_text)
    set_status("Pensando")
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
            # None sinaliza falha total pro chamador (handle_command) - uma
            # desculpa não é uma resposta de verdade e não deve ser salva no
            # cache de perguntas/respostas.
            return None


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
    save_conversation(command_text, answer)
    return answer
