import os

from dotenv import load_dotenv

load_dotenv()  # lê variáveis de um arquivo .env local (fora do Git), se existir

# Comparados sem acento (text_utils.normalize_text agora remove acentos),
# por isso aqui ficam só formas sem acento.
WAKE_WORDS = ["nico", "nicolo", "nick", "nic"]
WAKE_WORD_ALIASES = {
    "niko": "nico",
    "nikko": "nico",
    "nicco": "nico",
    "nicko": "nico",
    "nicola": "nico",
    "nicol": "nico",
    "nicole": "nico",
    "nichole": "nico",
    "nikolai": "nico",
    "neeko": "nico",
    "niku": "nico",
}

# --- Wake word offline (opcional, Picovoice Porcupine) ---------------------
# Ver wake_word.py para o que isso faz e como configurar (conta grátis,
# treinar uma wake word "Nico" customizada, baixar o .ppn). Vazio por
# padrão - sem isso, o Nico detecta a wake word do jeito original (nuvem).
PICOVOICE_ACCESS_KEY = os.environ.get("PICOVOICE_ACCESS_KEY", "")
PICOVOICE_KEYWORD_PATH = os.environ.get("PICOVOICE_KEYWORD_PATH", "")

DB_PATH = "nico_memory.db"

OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "qwen2.5:1.5b"
OLLAMA_TIMEOUT = 180
OLLAMA_TEMPERATURE = 0.3
# Corta a geração depois de ~90 tokens (respostas de voz são curtas mesmo)
# e mantém o modelo carregado na memória por 30 min entre usos, para não
# pagar o custo de recarregar o modelo a cada pergunta.
OLLAMA_NUM_PREDICT = 90
OLLAMA_KEEP_ALIVE = "30m"

# Voz local de fallback (pyttsx3/SAPI5), usada só se a voz neural falhar
# (ex.: sem internet). No Windows deste projeto só há vozes femininas
# instaladas (Maria/pt-BR, Zira/en-US) - como o Nico agora fala português,
# o fallback usa a Maria (pt-BR), que ao menos pronuncia o idioma certo
# (índice 1/Zira seria inglês lendo texto em português, pior ainda).
VOICE_INDEX = 0

# Voz neural (Microsoft Edge Read Aloud, via biblioteca edge-tts) - mais
# natural e masculina, é a voz principal do Nico. Precisa de internet.
# "pt-BR-AntonioNeural" é a única voz masculina em pt-BR disponível no
# edge-tts hoje (confirmado via edge_tts.list_voices()) - combina bem com
# a personalidade calma e cavalheiresca/estilo Jarvis pedida para o Nico.
NEURAL_VOICE = "pt-BR-AntonioNeural"
USE_NEURAL_VOICE = True

# Cache em disco dos áudios já gerados pela voz neural (chave = texto +
# voz). Acelera bastante frases repetidas (saudações, avisos de erro,
# "poderia terminar o que estava dizendo?" etc.), já que evita chamar o
# edge-tts de novo pela rede para algo que já foi falado antes.
USE_TTS_CACHE = True
TTS_CACHE_DIR = "tts_cache"

CONTEXT_HISTORY_LIMIT = 5

# Limiares da busca de memória por palavras-chave (similaridade de Jaccard).
MATCH_THRESHOLD = 0.6
AMBIGUITY_MARGIN = 0.15
MAX_CLARIFICATION_CANDIDATES = 2

# Heurística simples para detectar comando incompleto.
MIN_COMMAND_WORDS = 2
# Comparados sem acento (ver text_utils._strip_accents), por isso aqui vão
# sem acento mesmo ("nao" cobre "não", etc.).
INCOMPLETE_TRAILING_WORDS = {
    "e", "mas", "ou", "entao", "porque", "se", "que", "quando",
    "com", "para", "de", "do", "da", "o", "a", "um", "uma",
}

# Frases que indicam um pedido para o Nico guardar um fato pessoal (ex.:
# "lembre que tenho uma prova na sexta", "não esqueça da reunião às 5").
# "você lembra" / "do que você lembra" ficam de fora de propósito - isso é
# uma pergunta (recall), não um pedido pra guardar algo novo.
REMEMBER_TRIGGERS = (
    "me lembre de", "me lembra de", "nao esqueca", "anote que", "anota que",
    "lembre que", "lembra que", "lembre", "lembra",
)
REMEMBER_RECALL_PREFIXES = ("voce lembra", "do que voce lembra", "o que voce lembra")

# --- Lembretes com hora marcada ---------------------------------------------
# Quando um REMEMBER tem uma data/hora dentro (ex.: "lembre que tenho uma
# prova na sexta às 14h"), o Nico agenda um aviso de verdade (fala em voz
# alta) pra aquele horário, em vez de só guardar o fato.
REMINDER_TIMEZONE = "America/Sao_Paulo"
# Se o texto tiver uma data mas nenhuma hora explícita (ex.: só "Friday"),
# assume esse horário local como padrão para o lembrete.
REMINDER_DEFAULT_HOUR = 9
# A cada quantos segundos o Nico verifica se algum lembrete venceu.
REMINDER_CHECK_INTERVAL_SECONDS = 30

# "timer de 10 minutos", "cronômetro de 30 segundos" - um lembrete rápido,
# sem precisar passar pelo fluxo de REMEMBER. Reaproveita a mesma tabela
# de lembretes (ver reminders.schedule_timer()).
TIMER_TRIGGERS = ("timer", "cronometro", "alarme")

# "o que eu tenho hoje", "minha agenda" - lista os lembretes de hoje e,
# se configurado, os eventos de hoje do Google Calendar (ver google_calendar.py).
AGENDA_TRIGGERS = ("o que eu tenho hoje", "o que tenho hoje", "minha agenda", "agenda de hoje", "meus compromissos")

# Endereço secreto no formato iCal da sua agenda do Google Calendar (ver
# google_calendar.py para como conseguir). Vazio por padrão - sem isso, a
# agenda do Nico mostra só os lembretes que você mesma pediu pra guardar.
GOOGLE_CALENDAR_ICS_URL = os.environ.get("GOOGLE_CALENDAR_ICS_URL", "")

# "bom dia" - clima + agenda do dia numa única fala, estilo briefing matinal.
BRIEFING_TRIGGERS = ("bom dia", "resumo do dia", "me da um resumo", "me de um resumo")

# "quanto é 23 vezes 7" - calculadora (ver calculator.py). O gatilho sozinho
# não basta: só vira CALC se der pra extrair uma conta de verdade (ver
# commands.classify_command()), senão "quanto é a distância até a lua" cairia
# aqui por engano em vez de ir pro LLM.
CALC_TRIGGERS = ("quanto e", "quanto da", "calcule", "calcula", "qual o resultado de")

# --- Recursos estilo "Jarvis": abrir apps/sites, volume, print, bateria ----
# Apps conhecidos do Windows (nome falado -> comando pra abrir). Qualquer
# coisa fora dessa lista cai no SITE_SHORTCUTS ou, por último, numa busca
# no Google.
APP_SHORTCUTS = {
    "notepad": "notepad",
    "bloco de notas": "notepad",
    "calculator": "calc",
    "calculadora": "calc",
    "paint": "mspaint",
    "file explorer": "explorer",
    "explorer": "explorer",
    "explorador de arquivos": "explorer",
    "settings": "ms-settings:",
    "configuracoes": "ms-settings:",
    "task manager": "taskmgr",
    "gerenciador de tarefas": "taskmgr",
    "control panel": "control",
    "painel de controle": "control",
    "command prompt": "cmd",
    "prompt de comando": "cmd",
    "cmd": "cmd",
    "spotify": "spotify:",
}

SITE_SHORTCUTS = {
    "youtube": "https://youtube.com",
    "google": "https://google.com",
    "gmail": "https://mail.google.com",
    "github": "https://github.com",
    "whatsapp": "https://web.whatsapp.com",
    "netflix": "https://netflix.com",
    "twitter": "https://twitter.com",
    "x": "https://twitter.com",
    "reddit": "https://reddit.com",
    "wikipedia": "https://wikipedia.org",
    "instagram": "https://instagram.com",
    "facebook": "https://facebook.com",
    "tiktok": "https://tiktok.com",
    "linkedin": "https://linkedin.com",
    "discord": "https://discord.com/app",
    "telegram": "https://web.telegram.org",
    "twitch": "https://twitch.tv",
    "pinterest": "https://pinterest.com",
    "chrome": None,  # tratado à parte: abre uma aba em branco do navegador padrão
    "google chrome": None,
    "browser": None,
    "navegador": None,
}

# Vários jeitos naturais de pedir pra abrir algo em português - checados
# com startswith, então são prefixos completos (com o espaço no final).
OPEN_PREFIXES = ("abra ", "abrir ", "abre ")
OPEN_DOCUMENTATION_TRIGGERS = (
    "documentacao oficial de ", "documentacao oficial do ", "documentacao oficial da ",
    "documentacao de ", "documentacao do ", "documentacao da ",
    "docs oficiais de ", "docs de ", "docs do ", "docs da ",
)

# "toca X no youtube", "abre um vídeo de X no youtube", "procura X no
# youtube" - abre a busca do YouTube já com o termo (ver
# system_control.search_youtube()). Palavras removidas pra sobrar só o
# termo de busca de verdade.
YOUTUBE_SEARCH_FILLER_WORDS = {
    "abra", "abrir", "abre", "toca", "toque", "coloca", "coloque", "procura",
    "procure", "pesquisa", "pesquise", "busca", "busque", "um", "uma", "o",
    "a", "no", "do", "de", "por", "favor", "video", "youtube",
}

# --- "Modos de trabalho" (abrir vários sites/apps de uma vez) --------------
# "modo <nome>" (ex.: "modo trabalho", "modo estudos") abre, de uma vez,
# todos os sites/apps configurados para aquele modo - reaproveitando
# APP_SHORTCUTS/SITE_SHORTCUTS (ver system_control.open_target()).
# Cada modo vira uma variável de ambiente WORK_MODE_<NOME> no .env, com os
# itens separados por vírgula (ex.: WORK_MODE_TRABALHO=gmail,github,notion.so) -
# o nome depois de "WORK_MODE_" (em minúsculas) é o que você fala depois de
# "modo". (Isso substitui uma tentativa anterior de abrir Espaços de
# Trabalho nativos do Edge diretamente - inviável nesta versão do Edge,
# ver "Follow-up round 15" no AGENTS.md para o motivo.)
WORK_MODES = {
    key[len("WORK_MODE_"):].lower(): [item.strip() for item in value.split(",") if item.strip()]
    for key, value in os.environ.items()
    if key.startswith("WORK_MODE_") and value
}

# Controle de volume: em vez de exigir uma frase exata, basta a palavra
# "volume" (ou "som") aparecer em algum lugar da frase junto de uma destas
# palavras de direção, em qualquer ordem - assim "aumenta o volume",
# "coloca o som mais alto", "abaixa o volume" etc. todos batem.
VOLUME_KEYWORDS = {"volume", "som"}
VOLUME_UP_WORDS = {"aumenta", "aumentar", "aumente", "sobe", "suba", "alto", "mais"}
VOLUME_DOWN_WORDS = {"diminui", "diminuir", "diminua", "abaixa", "abaixe", "baixo", "reduz", "reduza", "menos"}
VOLUME_MUTE_WORDS = {"mudo", "mudar", "silencio", "silencia", "silencie"}
# Essas valem mesmo sem a palavra "volume"/"som" na frase (ex.: só "mudo"
# sozinho já é claro o suficiente).
VOLUME_MUTE_TRIGGERS = ("mudo", "silencio", "silencia")

SCREENSHOT_TRIGGERS = ("tira um print", "tire um print", "tirar um print", "captura de tela", "print da tela", "screenshot")
SCREENSHOT_FOLDER = "screenshots"

# "bateria" sozinho já é um gatilho claro e natural o suficiente (mesmo
# espírito da lição do round 11: preferir palavra-chave solta a frase exata).
BATTERY_TRIGGERS = ("bateria",)

# "clima"/"tempo" já estão em REALTIME_KEYWORDS (cai na busca web genérica),
# mas esses gatilhos pegam a pergunta antes disso, pra usar a API gratuita
# do Open-Meteo (mais rápida e confiável que busca + LLM pra isso).
WEATHER_TRIGGERS = ("previsao do tempo", "como esta o tempo", "vai chover", "esta chovendo", "clima", "quantos graus")
# Cidade padrão (opcional, lida do .env). Se vazia, o Nico tenta descobrir
# a cidade atual pelo IP (ip-api.com, grátis, sem chave).
WEATHER_CITY = os.environ.get("WEATHER_CITY", "")

# --- IA na nuvem (reforço para perguntas difíceis) -------------------------
# Chaves lidas do arquivo .env (nunca comitado - já está no .gitignore).
# Onde conseguir cada uma, de graça:
#   GROQ_API_KEY   -> https://console.groq.com/keys
#   GEMINI_API_KEY -> https://aistudio.google.com/apikey
#   TAVILY_API_KEY -> https://app.tavily.com (free tier, ~1000 buscas/mês)
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
# Modelo grande disponível na conta Groq do usuário no momento (confirmado
# via GET /v1/models). Modelos de IA saem de linha com frequência - se
# parar de funcionar, liste os disponíveis com esse mesmo endpoint.
GROQ_MODEL = "openai/gpt-oss-120b"

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
GEMINI_MODEL = "gemini-3.8-flash"

TAVILY_API_KEY = os.environ.get("TAVILY_API_KEY", "")

CLOUD_TIMEOUT = 30

# Palavras que indicam que a pergunta provavelmente precisa de informação
# atual/da internet (não apenas de um modelo de linguagem maior). Sem
# acento, como tudo que é comparado via normalize_text.
REALTIME_KEYWORDS = {
    "hoje", "agora", "atualmente", "atual", "ultimo", "ultima", "ultimas",
    "noticias", "clima", "tempo", "previsao", "preco", "precos", "cotacao",
    "placar", "eleicao", "acontecendo", "recente", "recentemente", "ontem",
}

# --- Documentos locais (pastas sincronizadas do Google Drive) --------------
# DOCUMENTS_FOLDER: uma tarefa agendada no Claude (rotina "Nico Research")
#   salva um resumo diário (Tecnologia, Política, Games, Animes, Mangás,
#   Manhwa) num arquivo por dia nessa pasta.
# NOTES_FOLDER: pasta de anotações manuais - solte arquivos .txt/.md/.docx
#   aqui com qualquer coisa que você queira que o Nico saiba.
# Ambas ficam vazias ("") até você configurar o Google Drive Desktop - sem
# elas, o Nico simplesmente pula essa fonte e segue funcionando normalmente.
DOCUMENTS_FOLDER = os.environ.get("DOCUMENTS_FOLDER", "")
NOTES_FOLDER = os.environ.get("NOTES_FOLDER", "")

# Lista de todas as pastas de documentos configuradas (vazias são
# ignoradas). Adicione mais aqui (e no .env) se quiser outra fonte além
# dessas duas - documents.py procura em todas elas.
DOCUMENT_FOLDERS = [folder for folder in (DOCUMENTS_FOLDER, NOTES_FOLDER) if folder]

DOCUMENT_MATCH_THRESHOLD = 0.15
DOCUMENT_SCAN_LIMIT = 30  # olha só os N arquivos mais recentes de cada pasta

# --- "Modo sério" (pesquisa de verdade e salva um relatório em arquivo) ----
# "pesquise sobre X" / "pesquisa sobre X" faz o Nico buscar na web (Tavily)
# e usar a nuvem (Groq/Gemini) pra escrever um relatório mais completo que
# uma resposta falada normal, e salva um PDF com apresentação inspirada na ABNT.
# Usa a pasta de anotações (NOTES_FOLDER) quando configurada, mantendo os PDFs
# também ficam disponíveis pro Nico reler depois (documents.py já escaneia
# essa pasta) - ou uma pasta local própria se NOTES_FOLDER não existir.
RESEARCH_TRIGGERS = (
    "modo pesquisa", "pesquise sobre", "pesquisa sobre",
    "faca uma pesquisa sobre", "pesquise a fundo sobre",
)
RESEARCH_FOLDER = NOTES_FOLDER or "pesquisas"
RESEARCH_MAX_RESULTS = 6

# --- Grafo de memória (estilo "mini galáxia") -------------------------------
# Pontuação mínima de similaridade (mesma escala de MATCH_THRESHOLD) para
# desenhar uma aresta entre duas memórias no grafo. É mais baixa que
# MATCH_THRESHOLD de propósito: no grafo queremos mostrar até conexões
# fracas entre assuntos parecidos, não só "é a mesma pergunta".
GRAPH_EDGE_THRESHOLD = 0.2
