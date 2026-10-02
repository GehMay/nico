import string
import unicodedata


def _strip_accents(text):
    """Remove acentos (á, ã, ç, é...) para que os gatilhos de comando não
    precisem cobrir toda variação de acentuação que o reconhecimento de voz
    pode (ou não) produzir - "não", "nao" e "NÃO" todos ficam "nao".
    """
    decomposed = unicodedata.normalize("NFD", text)
    return "".join(char for char in decomposed if unicodedata.category(char) != "Mn")


def normalize_text(text):
    clean_text = _strip_accents(text.lower())
    clean_text = clean_text.translate(str.maketrans("", "", string.punctuation))
    return " ".join(clean_text.split())


def tokenize(text):
    return normalize_text(text).split()


def is_incomplete_command(text, min_words, trailing_words):
    tokens = tokenize(text)
    if len(tokens) < min_words:
        return True
    if tokens and tokens[-1] in trailing_words:
        return True
    return False


def is_realtime_query(text, realtime_keywords):
    tokens = tokenize(text)
    return any(token in realtime_keywords for token in tokens)


# Frases educadas comuns antes de um pedido falado (ex.: "você pode abrir o
# Instagram", "poderia tirar uma captura de tela"). São removidas antes de
# checar os gatilhos de comando, senão "você pode abrir X" não seria
# reconhecido como um pedido para abrir X (só "abra X" bateria sozinho).
# Comparação feita sem acento (ver _strip_accents) para cobrir "você"/"voce".
_POLITE_PREFIXES = (
    "voce poderia por favor ", "voce podia por favor ",
    "voce poderia ", "voce podia ", "voce pode ",
    "poderia ", "podia ",
    "pode ",
    "por favor ",
)
_QUESTION_STARTERS = ("voce poderia", "voce podia", "voce pode", "poderia", "podia")


def strip_request_wrapper(text):
    """Remove uma frase educada do início da fala e diz se a frase original
    tinha formato de pergunta ("você pode abrir...?") em vez de ordem direta
    ("abra..."). Retorna (texto_sem_a_frase_educada, era_pergunta: bool).

    Isso é o que permite ao Nico reagir diferente: se foi perguntado
    ("você pode abrir o Instagram?"), confirma antes de agir ("Claro, abrindo
    o Instagram."); se foi uma ordem direta ("abra o Instagram"), só age
    ("Abrindo o Instagram."), sem precisar confirmar.
    """
    stripped = text.strip()
    lower = _strip_accents(stripped.lower())
    was_question = lower.startswith(_QUESTION_STARTERS)

    for prefix in _POLITE_PREFIXES:
        if lower.startswith(prefix):
            stripped = stripped[len(prefix):].strip()
            break

    return stripped, was_question
