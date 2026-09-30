import os

from dotenv import load_dotenv

load_dotenv()  # lê variáveis de um arquivo .env local (fora do Git), se existir

WAKE_WORDS = ["nico", "nicolò", "nicolo", "nick", "nic"]
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
# instaladas (Maria/pt-BR, Zira/en-US) - por isso o fallback não é
# masculino, mas ele só entra em ação se a voz neural não estiver
# disponível.
VOICE_INDEX = 1

# Voz neural (Microsoft Edge Read Aloud, via biblioteca edge-tts) - mais
# natural e masculina, é a voz principal do Nico. Precisa de internet.
# Outras opções masculinas em en-US: "en-US-ChristopherNeural",
# "en-US-EricNeural", "en-US-DavisNeural".
NEURAL_VOICE = "en-US-GuyNeural"
USE_NEURAL_VOICE = True

# Cache em disco dos áudios já gerados pela voz neural (chave = texto +
# voz). Acelera bastante frases repetidas (saudações, avisos de erro,
# "could you finish that thought?" etc.), já que evita chamar o edge-tts
# de novo pela rede para algo que já foi falado antes.
USE_TTS_CACHE = True
TTS_CACHE_DIR = "tts_cache"

CONTEXT_HISTORY_LIMIT = 5

# Limiares da busca de memória por palavras-chave (similaridade de Jaccard).
MATCH_THRESHOLD = 0.6
AMBIGUITY_MARGIN = 0.15
MAX_CLARIFICATION_CANDIDATES = 2

# Heurística simples para detectar comando incompleto.
MIN_COMMAND_WORDS = 2
INCOMPLETE_TRAILING_WORDS = {
    "and", "but", "or", "so", "because", "if", "that", "which", "when",
    "with", "to", "of", "the", "a", "an",
}

# Frases que indicam um pedido para o Nico guardar um fato pessoal (ex.:
# "remember I have a test Friday", "don't forget my meeting at 5").
# "do you remember" / "what do you remember" ficam de fora de propósito -
# isso é uma pergunta (recall), não um pedido pra guardar algo novo.
REMEMBER_TRIGGERS = ("remind me", "don't forget", "note that", "remember")
REMEMBER_RECALL_PREFIXES = ("do you remember", "what do you remember", "can you remember what")

# --- Notificações via Telegram (CallMeBot, grátis) --------------------------
# CallMeBot manda uma mensagem de texto pro seu Telegram via uma requisição
# HTTP simples, sem precisar de chave de API - só precisa autorizar o bot
# uma vez (mandando /start pra @CallMeBot_txtbot no Telegram).
# TELEGRAM_USER = seu username do Telegram (sem @), lido do .env.
TELEGRAM_USER = os.environ.get("TELEGRAM_USER", "")
TELEGRAM_API_URL = "https://api.callmebot.com/text.php"

# Frases que pedem pro Nico mandar uma mensagem/avisar no celular.
NOTIFY_TRIGGERS = ("text my phone", "message my phone", "notify my phone", "send me a message")

# --- Lembretes com hora marcada ---------------------------------------------
# Quando um REMEMBER tem uma data/hora dentro (ex.: "remember I have a test
# Friday at 2pm"), o Nico agenda um aviso de verdade (Telegram + fala em voz
# alta) pra aquele horário, em vez de só guardar o fato.
REMINDER_TIMEZONE = "America/Sao_Paulo"
# Se o texto tiver uma data mas nenhuma hora explícita (ex.: só "Friday"),
# assume esse horário local como padrão para o lembrete.
REMINDER_DEFAULT_HOUR = 9
# A cada quantos segundos o Nico verifica se algum lembrete venceu.
REMINDER_CHECK_INTERVAL_SECONDS = 30

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
# atual/da internet (não apenas de um modelo de linguagem maior).
REALTIME_KEYWORDS = {
    "today", "now", "currently", "current", "latest", "news", "weather",
    "forecast", "price", "prices", "stock", "stocks", "score", "election",
    "happening", "recent", "recently", "yesterday", "tonight",
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

# --- Grafo de memória (estilo "mini galáxia") -------------------------------
# Pontuação mínima de similaridade (mesma escala de MATCH_THRESHOLD) para
# desenhar uma aresta entre duas memórias no grafo. É mais baixa que
# MATCH_THRESHOLD de propósito: no grafo queremos mostrar até conexões
# fracas entre assuntos parecidos, não só "é a mesma pergunta".
GRAPH_EDGE_THRESHOLD = 0.2
