from flask import Flask, jsonify, request, send_from_directory

import state
from commands import handle_command
from config import GRAPH_EDGE_THRESHOLD
from database import fetch_all_conversations
from memory import keyword_score
from text_utils import tokenize

app = Flask(__name__, static_folder="web", static_url_path="/assets")


@app.route("/")
def index():
    return send_from_directory(app.static_folder, "index.html")


@app.route("/memory")
def memory_page():
    return send_from_directory(app.static_folder, "memory.html")


@app.route("/status")
def status():
    return jsonify(status=state.get_status())


@app.route("/history")
def history():
    return jsonify(history=state.conversation_history[-20:])


@app.route("/api/memory")
def api_memory():
    rows = fetch_all_conversations()
    return jsonify(memory=[{"question": q, "answer": a} for q, a in rows])


@app.route("/api/memory/graph")
def api_memory_graph():
    rows = fetch_all_conversations()
    tokenized = [tokenize(question) for question, _ in rows]

    nodes = [
        {
            "id": index,
            "label": (question[:42] + "…") if len(question) > 42 else question,
            "question": question,
            "answer": answer,
        }
        for index, (question, answer) in enumerate(rows)
    ]

    edges = []
    for i in range(len(rows)):
        for j in range(i + 1, len(rows)):
            score = keyword_score(tokenized[i], tokenized[j])
            if score >= GRAPH_EDGE_THRESHOLD:
                edges.append({"from": i, "to": j, "value": round(score, 3)})

    return jsonify(nodes=nodes, edges=edges)


@app.route("/command", methods=["POST"])
def command():
    data = request.get_json(force=True, silent=True) or {}
    text = (data.get("text") or "").strip()
    if not text:
        return jsonify(error="empty text"), 400

    result = handle_command(text, state.conversation_history)
    return jsonify(kind=result.kind, answer=result.text)


def run_web_server(host="0.0.0.0", port=5000):
    app.run(host=host, port=port, debug=False, use_reloader=False)
