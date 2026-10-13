"""Geração de código via Kimi ("crie um site/projeto sobre X").

Decisão de segurança deliberada: os arquivos gerados são sempre escritos
numa pasta separada (`config.PROJECTS_FOLDER`), nunca nos arquivos reais do
Nico, e nunca são executados automaticamente - nem aqui, nem em nenhum
outro lugar deste projeto. Uma "sugestão de melhoria pro próprio Nico" usa
exatamente o mesmo caminho: vira um rascunho nessa pasta, pronto pra
revisão humana (e, se for pra entrar de verdade no Nico, uma conversa
normal pedindo pro Claude revisar e aplicar) - não um ciclo de
autoprogramação sem revisão. Ver "Follow-up round 33" no AGENTS.md para o
raciocínio completo por trás dessa decisão.
"""
import datetime
import os
import re

from cloud_llm import ask_kimi
from config import (
    CODE_GEN_TIMEOUT,
    MAX_PROJECT_FILE_BYTES,
    MAX_PROJECT_FILES,
    PROJECTS_FOLDER,
)

CODE_SYSTEM_PROMPT = (
    "Você é um gerador de código. Gere um projeto pequeno, completo e "
    "funcional a partir do pedido do usuário. Não invente requisitos que "
    "não foram pedidos, e não deixe partes incompletas ou com placeholders "
    "do tipo 'implemente aqui'.\n\n"
    "Responda SOMENTE com os arquivos do projeto, cada um exatamente neste "
    "formato, sem nenhum texto fora disso:\n\n"
    "### ARQUIVO: caminho/do/arquivo.ext\n"
    "```\n"
    "conteúdo completo do arquivo\n"
    "```\n\n"
    "Pode repetir esse bloco para cada arquivo (ex.: index.html, style.css, "
    "script.js, README.md). Caminhos de arquivo devem ser relativos, sem "
    "'..' e sem letra de unidade - tudo dentro de uma única pasta do "
    "projeto. Não use markdown fora dos blocos de código."
)

_FILE_BLOCK_RE = re.compile(
    r"###\s*ARQUIVO:\s*(?P<path>[^\n]+)\n```[a-zA-Z0-9_+-]*\n(?P<content>.*?)```",
    re.DOTALL,
)


def _safe_filename_slug(text, max_length=40):
    cleaned = "".join(char for char in text if char.isalnum() or char in " -_").strip()
    cleaned = "-".join(cleaned.split())
    return cleaned[:max_length] or "projeto"


def _is_safe_relative_path(path):
    path = path.strip().replace("\\", "/")
    if not path or path.startswith("/") or ".." in path.split("/"):
        return False
    if re.match(r"^[a-zA-Z]:", path):  # letra de unidade do Windows (ex.: C:)
        return False
    return True


def _parse_files(response_text):
    files = {}
    for match in _FILE_BLOCK_RE.finditer(response_text):
        path = match.group("path").strip()
        content = match.group("content")
        if not _is_safe_relative_path(path):
            print(f"Ignorando caminho de arquivo inseguro sugerido pelo modelo: {path!r}")
            continue
        if len(content.encode("utf-8")) > MAX_PROJECT_FILE_BYTES:
            print(f"Ignorando arquivo grande demais: {path!r}")
            continue
        files[path] = content
        if len(files) >= MAX_PROJECT_FILES:
            break
    return files


def build_project(description):
    """Gera um projeto a partir da descrição pedida e salva em uma subpasta
    nova e isolada dentro de `config.PROJECTS_FOLDER`. Nunca executa nada.
    Devolve o caminho da pasta criada.

    Levanta RuntimeError se o Kimi não estiver configurado, se a chamada
    falhar, ou se a resposta não contiver nenhum arquivo reconhecível.
    """
    prompt = f"Pedido do usuário: {description}"
    response_text = ask_kimi(prompt, system_prompt=CODE_SYSTEM_PROMPT, timeout=CODE_GEN_TIMEOUT)

    files = _parse_files(response_text)
    if not files:
        raise RuntimeError("O modelo não devolveu nenhum arquivo reconhecível.")

    timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    project_dir = os.path.join(PROJECTS_FOLDER, f"{timestamp}_{_safe_filename_slug(description)}")
    os.makedirs(project_dir, exist_ok=True)

    for relative_path, content in files.items():
        full_path = os.path.join(project_dir, relative_path)
        os.makedirs(os.path.dirname(full_path) or project_dir, exist_ok=True)
        with open(full_path, "w", encoding="utf-8") as handle:
            handle.write(content)

    return project_dir
