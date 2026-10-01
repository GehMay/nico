import string


def normalize_text(text):
    clean_text = text.lower()
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


# Frases educadas comuns antes de um pedido falado (ex.: "can you open
# Instagram", "could you please take a screenshot"). São removidas antes de
# checar os gatilhos de comando, senão "can you open X" não seria
# reconhecido como um pedido para abrir X (só "open X" batia antes).
_POLITE_PREFIXES = (
    "could you please ", "can you please ", "would you please ", "will you please ",
    "could you ", "can you ", "would you ", "will you ",
    "please ",
)
_QUESTION_STARTERS = ("could you", "can you", "would you", "will you")


def strip_request_wrapper(text):
    """Remove uma frase educada do início da fala e diz se a frase original
    tinha formato de pergunta ("can you...?") em vez de ordem direta
    ("open..."). Retorna (texto_sem_a_frase_educada, era_pergunta: bool).

    Isso é o que permite ao Nico reagir diferente: se foi perguntado
    ("can you open Instagram?"), confirma antes de agir ("Sure, opening
    Instagram."); se foi uma ordem direta ("open Instagram"), só age
    ("Opening Instagram."), sem precisar confirmar.
    """
    stripped = text.strip()
    lower = stripped.lower()
    was_question = lower.startswith(_QUESTION_STARTERS)

    for prefix in _POLITE_PREFIXES:
        if lower.startswith(prefix):
            stripped = stripped[len(prefix):].strip()
            break

    return stripped, was_question
