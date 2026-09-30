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
