import requests

from config import CLOUD_TIMEOUT, TAVILY_API_KEY

TAVILY_URL = "https://api.tavily.com/search"


def search_web(query, max_results=4):
    if not TAVILY_API_KEY:
        raise RuntimeError("TAVILY_API_KEY is not configured")

    response = requests.post(
        TAVILY_URL,
        json={
            "api_key": TAVILY_API_KEY,
            "query": query,
            "max_results": max_results,
            "include_answer": False,
        },
        timeout=CLOUD_TIMEOUT,
    )
    response.raise_for_status()
    return response.json().get("results", [])


def build_search_prompt(command_text, results):
    if not results:
        return command_text

    snippets = "\n".join(
        f"- {result.get('title', '')}: {result.get('content', '')[:300]}"
        for result in results
    )
    return (
        "Use the web search results below to answer the question. "
        "Reply in under three sentences, natural spoken English.\n\n"
        f"Search results:\n{snippets}\n\n"
        f"Question: {command_text}\n"
        "Answer:"
    )
