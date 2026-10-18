import threading

from flask import Flask, jsonify, request, send_from_directory

import state
from commands import handle_command
from config import GRAPH_EDGE_THRESHOLD
from database import delete_all_conversations, delete_conversation, fetch_all_conversations
from memory import keyword_score
from text_utils import tokenize
from tts import speak

app = Flask(__name__, static_folder="web", static_url_path="/assets")
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024
_ALLOWED_LOOPBACK_HOSTS = {"127.0.0.1", "127.0.0.1:5000", "localhost", "localhost:5000"}


def _is_same_origin_request():
    if request.host.lower() not in _ALLOWED_LOOPBACK_HOSTS:
        return False
    origin = request.headers.get("Origin")
    if origin is None or origin.rstrip("/") != request.host_url.rstrip("/"):
        return False
    return request.headers.get("X-Nico-Request") == "1"


@app.after_request
def _add_security_headers(response):
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "script-src 'self' https://cdn.jsdelivr.net https://unpkg.com; "
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
        "font-src https://fonts.gstatic.com; img-src 'self' data: blob:; "
        "worker-src 'self' blob:; connect-src 'self'"
    )
    return response


@app.route("/")
def index():
    return send_from_directory(app.static_folder, "index.html")


@app.route("/memory")
def memory_page():
    return send_from_directory(app.static_folder, "memory.html")


@app.route("/status")
def status():
    return jsonify(status=state.get_status(), mic_enabled=state.is_mic_enabled())


@app.route("/mic/toggle", methods=["POST"])
def mic_toggle():
    if not _is_same_origin_request():
        return jsonify(error="forbidden request"), 403
    state.set_mic_enabled(not state.is_mic_enabled())
    return jsonify(mic_enabled=state.is_mic_enabled())


@app.route("/history")
def history():
    return jsonify(history=state.conversation_history[-20:])


@app.route("/api/memory")
def api_memory():
    rows = fetch_all_conversations()
    return jsonify(memory=[{"id": i, "question": q, "answer": a} for i, q, a in rows])


@app.route("/api/memory/graph")
def api_memory_graph():
    rows = fetch_all_conversations()
    tokenized = [tokenize(question) for _id, question, _answer in rows]

    # O id do nó é o id real da linha no banco (não a posição na lista), já
    # que o front usa esse id para pedir a exclusão de uma memória específica
    # (DELETE /api/memory/<id>) - um índice posicional mudaria toda vez que
    # outra memória fosse apagada.
    nodes = [
        {
            "id": conversation_id,
            "label": (question[:42] + "…") if len(question) > 42 else question,
            "question": question,
            "answer": answer,
        }
        for conversation_id, question, answer in rows
    ]

    edges = []
    for i in range(len(rows)):
        for j in range(i + 1, len(rows)):
            score = keyword_score(tokenized[i], tokenized[j])
            if score >= GRAPH_EDGE_THRESHOLD:
                edges.append({"from": rows[i][0], "to": rows[j][0], "value": round(score, 3)})

    return jsonify(nodes=nodes, edges=edges)


@app.route("/api/memory/<int:conversation_id>", methods=["DELETE"])
def api_memory_delete(conversation_id):
    """Apaga uma memória específica (botão "apagar" da galáxia), pelo id
    real da linha no banco. Só fatos/lembretes continuam intactos - essa
    tabela é só o cache de perguntas e respostas."""
    if not _is_same_origin_request():
        return jsonify(error="forbidden request"), 403
    delete_conversation(conversation_id)
    return jsonify(deleted=conversation_id)


@app.route("/api/memory", methods=["DELETE"])
def api_memory_delete_all():
    """Apaga toda a memória de conversas de uma vez (botão "apagar tudo")."""
    if not _is_same_origin_request():
        return jsonify(error="forbidden request"), 403
    delete_all_conversations()
    return jsonify(deleted="all")


@app.route("/command", methods=["POST"])
def command():
    if not _is_same_origin_request():
        return jsonify(error="forbidden request"), 403
    if not request.is_json:
        return jsonify(error="application/json required"), 415

    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify(error="JSON object required"), 400

    text = data.get("text")
    if not isinstance(text, str):
        return jsonify(error="text must be a string"), 400
    text = text.strip()
    if not text:
        return jsonify(error="empty text"), 400
    if len(text) > 3000:
        return jsonify(error="command too long"), 413

    result = handle_command(text, state.conversation_history)

    # Guarda no histórico compartilhado (mostrado no transcript do HUD) -
    # antes isso só acontecia quando a pergunta caía no caminho do LLM
    # (cache miss), então comandos como "que horas são" ou "bom dia"
    # nunca apareciam no chat, embora respondessem normalmente.
    state.conversation_history.append((text, result.text))

    # Fala a resposta em voz alta mesmo vindo do chat/painel escrito (não só
    # de comandos de voz) - roda numa thread à parte pra não atrasar a
    # resposta HTTP esperando o áudio terminar de tocar. Independe do
    # microfone estar pausado ou não: o botão de pausa só afeta a escuta.
    threading.Thread(target=speak, args=(result.text, state.set_status), daemon=True).start()

    return jsonify(kind=result.kind, answer=result.text)


def run_web_server(host="127.0.0.1", port=5000):
    app.run(host=host, port=port, debug=False, use_reloader=False)
