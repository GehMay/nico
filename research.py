import datetime
import os
import re
from urllib.parse import urlparse
from xml.sax.saxutils import escape

from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

from cloud_llm import ask_cloud_fallback
from config import RESEARCH_FOLDER, RESEARCH_MAX_RESULTS, TAVILY_API_KEY
from web_search import search_web

# Diferente da conversa normal (respostas curtas, faladas), um relatório de
# pesquisa é pra ser lido depois - por isso usa seu próprio prompt de
# sistema em vez do padrão curto do cloud_llm.
RESEARCH_SYSTEM_PROMPT = (
    "Você escreve relatórios de pesquisa em português do Brasil, não respostas "
    "faladas. Use linguagem clara, impessoal e organizada, com estrutura "
    "acadêmica de leitura inspirada nas normas ABNT. Baseie cada afirmação "
    "somente nas fontes fornecidas; indique citações numéricas como [1] junto "
    "às afirmações correspondentes. Não invente autores, datas, dados ou "
    "referências. Evite Markdown, floreios e repetição."
)


def _build_search_queries(topic, wanted, excluded):
    base_terms = [part.strip() for part in (topic, wanted) if part and part.strip()]
    exclusion_terms = [
        term.strip(" .,-:;!?")
        for term in re.split(r"[,;]|\b(?:e|ou)\b", excluded)
        if term.strip() and len(term.strip()) > 2
    ]

    queries = [
        " ".join(base_terms),
        f"{topic} {wanted} dados recentes",
        f"{topic} {wanted} principais pontos",
        f"{topic} {wanted} análise"
    ]

    if exclusion_terms:
        negative = " ".join(f'-{term}' for term in exclusion_terms[:3])
        queries.append(f"{topic} {wanted} {negative}")

    dedup = []
    seen = set()
    for query in queries:
        normalized = " ".join(query.split())
        if normalized and normalized.lower() not in seen:
            dedup.append(normalized)
            seen.add(normalized.lower())
    return dedup


def _build_research_prompt(topic, wanted, excluded, results):
    snippets = "\n".join(
        f"[{index}] {result.get('title', '')} ({result.get('url', '')}): "
        f"{result.get('content', '')[:1200]}"
        for index, result in enumerate(results, start=1)
    )
    return (
        "Escreva um relatório de pesquisa completo e bem fundamentado. "
        "Use exclusivamente as fontes fornecidas e não omita limitações. "
        "Se as fontes forem insuficientes para algum ponto, diga isso claramente. "
        "Siga exatamente esta sequência: RESUMO, PALAVRAS-CHAVE, 1 INTRODUÇÃO, "
        "2 DESENVOLVIMENTO, 3 CONSIDERAÇÕES FINAIS. Cite as fontes no texto com "
        "[1], [2], [3], e assim por diante. Não invente autores, datas, dados, "
        "ou referências. Não use Markdown.\n\n"
        f"Tema: {topic}\n"
        f"O que o usuário quer: {wanted}\n"
        f"O que o usuário não quer: {excluded}\n\n"
        f"Resultados de pesquisa (fontes reais):\n{snippets}\n\n"
        "Conteúdo do relatório:"
    )


def _safe_filename_part(text, max_length=60):
    cleaned = "".join(char for char in text if char.isalnum() or char in " -_").strip()
    return cleaned[:max_length] or "pesquisa"


def _is_report_heading(line):
    heading = line.strip().strip("#* ").upper()
    if heading in {
        "RESUMO",
        "ABSTRACT",
        "1 INTRODUÇÃO",
        "1. INTRODUÇÃO",
        "2 DESENVOLVIMENTO",
        "2. DESENVOLVIMENTO",
        "3 CONSIDERAÇÕES FINAIS",
        "3. CONSIDERAÇÕES FINAIS",
    }:
        return True
    return bool(re.match(r"^\d+(?:\.\d+)*\s+[A-ZÁÉÍÓÚÂÊÔÃÕÇ]", heading))


def _write_research_pdf(topic, report, results, path, researched_at):
    body_style = ParagraphStyle(
        "ReportBody", fontName="Times-Roman", fontSize=12, leading=18,
        alignment=TA_JUSTIFY, firstLineIndent=1.25 * cm, spaceAfter=0,
    )
    heading_style = ParagraphStyle(
        "ReportHeading", fontName="Times-Bold", fontSize=12, leading=18,
        alignment=TA_LEFT, spaceBefore=12, spaceAfter=6, keepWithNext=True,
    )
    keyword_style = ParagraphStyle(
        "ReportKeywords", fontName="Times-Roman", fontSize=12, leading=18,
        alignment=TA_LEFT, firstLineIndent=0, spaceBefore=6, spaceAfter=6,
    )
    reference_style = ParagraphStyle(
        "ReportReference", fontName="Times-Roman", fontSize=10, leading=12,
        alignment=TA_LEFT, leftIndent=1.25 * cm, firstLineIndent=-1.25 * cm,
        spaceAfter=6,
    )
    title_style = ParagraphStyle(
        "ReportTitle", fontName="Times-Bold", fontSize=14, leading=18,
        alignment=TA_CENTER, spaceAfter=18,
    )
    metadata_style = ParagraphStyle(
        "ReportMetadata", fontName="Times-Roman", fontSize=10, leading=12,
        alignment=TA_CENTER, spaceAfter=18,
    )

    def draw_page_number(canvas, doc):
        canvas.saveState()
        canvas.setFont("Times-Roman", 10)
        canvas.drawCentredString(A4[0] / 2, 1.25 * cm, str(doc.page))
        canvas.restoreState()

    document = SimpleDocTemplate(
        path, pagesize=A4, topMargin=3 * cm, leftMargin=3 * cm,
        bottomMargin=2 * cm, rightMargin=2 * cm,
        title=f"Pesquisa - {topic}",
    )
    story = [
        Spacer(1, 0.8 * cm),
        Paragraph(escape(topic.strip()), title_style),
        Paragraph(
            f"Relatório de pesquisa | {researched_at.strftime('%d/%m/%Y')}",
            metadata_style,
        ),
    ]
    skipped_model_references = False
    for raw_line in report.splitlines():
        line = raw_line.strip().strip("# ")
        if not line:
            continue
        if line.upper().startswith("TÍTULO:"):
            continue
        if line.upper().strip("*:") in {"REFERÊNCIAS", "FONTES"}:
            skipped_model_references = True
            continue
        if skipped_model_references:
            continue
        if line.upper().startswith("PALAVRAS-CHAVE:"):
            label, value = line.split(":", 1)
            story.append(Paragraph(
                f"<b>{escape(label)}:</b> {escape(value.strip())}",
                keyword_style,
            ))
        elif _is_report_heading(line):
            story.append(Paragraph(escape(line.strip("#* ")), heading_style))
        elif line.startswith(("- ", "• ")):
            story.append(Paragraph(f"&#8226; {escape(line[2:].strip())}", body_style))
        else:
            story.append(Paragraph(escape(line), body_style))

    story.append(Spacer(1, 12))
    story.append(Paragraph("REFERÊNCIAS", heading_style))

    accessed = researched_at.strftime("%d/%m/%Y")
    for index, result in enumerate(results, start=1):
        url = result.get("url", "")
        domain = urlparse(url).netloc.removeprefix("www.")
        title_text = result.get("title", "Fonte consultada").strip()
        text = f"[{index}] {title_text}. {domain}. Disponível em: {url}. Acesso em: {accessed}."
        story.append(Paragraph(escape(text), reference_style))

    document.build(story, onFirstPage=draw_page_number, onLaterPages=draw_page_number)


def run_research(topic, wanted, excluded):
    """Pesquisa um tópico na web (Tavily) e usa a nuvem (Groq/Gemini) para
    escrever um relatório PDF com estrutura e apresentação inspiradas na ABNT.
    Retorna o caminho do arquivo salvo. Levanta uma exceção se a busca ou
    a nuvem falharem - quem chama decide a mensagem de erro para o usuário.
    """
    if not all(value.strip() for value in (topic, wanted, excluded)):
        raise ValueError("tema, objetivo e exclusões são obrigatórios")

    if not TAVILY_API_KEY:
        raise RuntimeError("TAVILY_API_KEY nao configurada - pesquisa na web indisponivel")

    queries = _build_search_queries(topic, wanted, excluded)
    combined = []
    seen_urls = set()
    for query in queries:
        results = search_web(query, max_results=max(3, RESEARCH_MAX_RESULTS // len(queries)))
        for result in results:
            url = (result or {}).get("url")
            if not url or url in seen_urls:
                continue
            seen_urls.add(url)
            combined.append(result)
        if len(combined) >= RESEARCH_MAX_RESULTS:
            break

    if not combined:
        raise RuntimeError(f"busca na web nao retornou resultados para '{topic}'")

    prompt = _build_research_prompt(topic, wanted, excluded, combined[:RESEARCH_MAX_RESULTS])
    report = ask_cloud_fallback(prompt, system_prompt=RESEARCH_SYSTEM_PROMPT)

    os.makedirs(RESEARCH_FOLDER, exist_ok=True)
    now = datetime.datetime.now()
    timestamp = now.strftime("%Y-%m-%d %H-%M")
    filename = f"{timestamp} - Pesquisa - {_safe_filename_part(topic)}.pdf"
    path = os.path.join(RESEARCH_FOLDER, filename)
    _write_research_pdf(topic, report, combined[:RESEARCH_MAX_RESULTS], path, now)

    return path
