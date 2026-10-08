import glob
import os

import docx
from pypdf import PdfReader

from config import DOCUMENT_FOLDERS, DOCUMENT_MATCH_THRESHOLD, DOCUMENT_SCAN_LIMIT
from memory import keyword_score
from text_utils import tokenize


def _list_recent_files():
    files = []
    for folder in DOCUMENT_FOLDERS:
        if not folder or not os.path.isdir(folder):
            continue

        paths = glob.glob(os.path.join(folder, "*.txt"))
        paths += glob.glob(os.path.join(folder, "*.md"))
        paths += glob.glob(os.path.join(folder, "*.docx"))
        paths += glob.glob(os.path.join(folder, "*.pdf"))
        # Arquivos como "YYYY-MM-DD - ...txt" ficam ordenados por data ao
        # ordenar o nome; para anotações manuais sem data no nome, isso só
        # vira uma ordem alfabética, o que não é um problema aqui.
        paths.sort(reverse=True)
        files.extend(paths[:DOCUMENT_SCAN_LIMIT])

    return files


def _read_text_sections(path):
    try:
        with open(path, "r", encoding="utf-8") as file:
            text = file.read()
    except OSError:
        return []
    return [block.strip() for block in text.split("\n\n") if block.strip()]


def _read_docx_sections(path):
    try:
        document = docx.Document(path)
    except Exception:
        return []

    sections = []
    current = []
    for paragraph in document.paragraphs:
        text = paragraph.text.strip()
        if not text:
            if current:
                sections.append(" ".join(current))
                current = []
            continue
        current.append(text)
    if current:
        sections.append(" ".join(current))

    return sections


def _read_sections(path):
    extension = os.path.splitext(path)[1].lower()
    if extension == ".docx":
        return _read_docx_sections(path)
    if extension == ".pdf":
        try:
            reader = PdfReader(path)
            sections = []
            for page in reader.pages:
                text = (page.extract_text() or "").strip()
                if text:
                    sections.append(text)
            return sections
        except Exception:
            return []
    return _read_text_sections(path)


def search_documents(query_text, max_results=5):
    """Procura trechos relevantes nos documentos locais configurados
    (DOCUMENT_FOLDERS). Retorna uma lista de (score, nome_do_arquivo, trecho).
    """
    query_tokens = tokenize(query_text)
    if not query_tokens:
        return []

    matches = []
    for path in _list_recent_files():
        for section in _read_sections(path):
            score = keyword_score(query_tokens, tokenize(section))
            if score >= DOCUMENT_MATCH_THRESHOLD:
                matches.append((score, os.path.basename(path), section))

    matches.sort(key=lambda item: item[0], reverse=True)
    return matches[:max_results]


def build_document_prompt(command_text, matches):
    snippets = "\n\n".join(f"(from {name}):\n{section}" for _, name, section in matches)
    return (
        "Use as notas abaixo, dos documentos de pesquisa salvos pelo "
        "usuário, para responder à pergunta. Responda em português do "
        "Brasil, em até três frases, de forma natural para fala.\n\n"
        f"Notas:\n{snippets}\n\n"
        f"Pergunta: {command_text}\n"
        "Resposta:"
    )
