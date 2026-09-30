from database import fetch_all_facts
from memory import keyword_score
from text_utils import tokenize


def search_facts(query_text, max_results=5):
    """Procura fatos salvos pelo usuário (via 'remember ...') relevantes
    para a pergunta atual. Retorna uma lista de (score, fact_text).
    """
    query_tokens = tokenize(query_text)
    if not query_tokens:
        return []

    matches = []
    for fact_text, _created_at in fetch_all_facts():
        score = keyword_score(query_tokens, tokenize(fact_text))
        if score > 0:
            matches.append((score, fact_text))

    matches.sort(key=lambda item: item[0], reverse=True)
    return matches[:max_results]


def build_facts_prompt(command_text, matches):
    facts_list = "\n".join(f"- {fact_text}" for _, fact_text in matches)
    return (
        "The user previously asked you to remember the facts below. Use "
        "them to answer the question if relevant. Reply in under three "
        "sentences, natural spoken English.\n\n"
        f"Remembered facts:\n{facts_list}\n\n"
        f"Question: {command_text}\n"
        "Answer:"
    )
