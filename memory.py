from dataclasses import dataclass, field
from typing import List, Optional, Tuple

from config import AMBIGUITY_MARGIN, MATCH_THRESHOLD, MAX_CLARIFICATION_CANDIDATES
from database import fetch_all_conversations
from text_utils import tokenize


@dataclass
class MemoryResult:
    status: str  # "hit", "ambiguous" ou "miss"
    answer: Optional[str] = None
    candidates: List[Tuple[str, str]] = field(default_factory=list)


def keyword_score(query_tokens, candidate_tokens):
    """Similaridade de Jaccard entre dois conjuntos de tokens (0.0 a 1.0).

    Usada tanto para achar uma memória em cache (find_conversation) quanto
    para desenhar as arestas do grafo de memória (ver web_server.py).
    """
    if not query_tokens or not candidate_tokens:
        return 0.0
    query_set = set(query_tokens)
    candidate_set = set(candidate_tokens)
    union = query_set | candidate_set
    if not union:
        return 0.0
    return len(query_set & candidate_set) / len(union)


def find_conversation(user_text):
    query_tokens = tokenize(user_text)
    if not query_tokens:
        return MemoryResult(status="miss")

    scored = []
    for _conversation_id, saved_question, saved_answer in fetch_all_conversations():
        score = keyword_score(query_tokens, tokenize(saved_question))
        if score > 0:
            scored.append((score, saved_question, saved_answer))

    if not scored:
        return MemoryResult(status="miss")

    scored.sort(key=lambda item: item[0], reverse=True)
    best_score, _, best_answer = scored[0]

    if best_score < MATCH_THRESHOLD:
        return MemoryResult(status="miss")

    second_score = scored[1][0] if len(scored) > 1 else 0.0
    is_ambiguous = (
        second_score >= MATCH_THRESHOLD - AMBIGUITY_MARGIN
        and best_score - second_score < AMBIGUITY_MARGIN
    )
    if is_ambiguous:
        candidates = [(q, a) for _, q, a in scored[:MAX_CLARIFICATION_CANDIDATES]]
        return MemoryResult(status="ambiguous", candidates=candidates)

    return MemoryResult(status="hit", answer=best_answer)
