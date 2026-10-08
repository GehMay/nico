# Nico Project Guide

## Purpose

Nico is a local Portuguese (Brazilian) voice assistant for Windows, originally started as a personal
learning project. The user decided that learning Python through this project was not working for
them and asked for the project to be finished directly, so they can study Python separately through
basic, dedicated exercises instead. As of this update, the project is considered functionally
finished: all previously planned phases are implemented and the codebase is in a working, reasonably
robust state. Further changes are done directly by Claude on request, without the incremental-teaching
workflow described below.

Nico's personality is calm, attentive, discreet, perceptive, and courteous, with light humor when
appropriate. He adapts his tone to the situation: candid and helpful when something fails, honest
about uncertainty, empathetic with sensitive topics, and natural rather than theatrical. He does not
claim real human feelings or experiences. Keep responses in Brazilian Portuguese unless the user
requests another language.

## Current Stack

- Python 3.11
- SpeechRecognition with Google recognition (`pt-BR`)
- edge-tts (Microsoft Edge neural voice, `pt-BR-AntonioNeural` - the only male pt-BR voice edge-tts
  currently offers) as the primary voice, pygame for playback; pyttsx3 kept only as an offline
  fallback voice (uses the Maria/pt-BR system voice, index 0, so the fallback is at least in the
  right language even though it sounds more robotic)
- pywebview as the desktop window shell (renders the HTML/CSS/JS HUD via the Windows WebView2
  runtime, built into Windows 11) - CustomTkinter/Tkinter are no longer used
- Flask local web server: serves the HUD UI, the memory galaxy, and the phone/tablet companion panel
  (same pages, all responsive)
- vis-network (JS, via CDN) for the memory graph, styled as a "galaxy" (dark background, glowing
  node dots, force-directed layout)
- Ollama with the local model `qwen2.5:1.5b` for everyday chat
- Optional cloud reinforcement for harder questions: Groq (primary) and Google Gemini (fallback if
  Groq fails), plus Tavily for real web search on time-sensitive questions - all free-tier, all
  optional (Nico works fine with none of them configured, just without that reinforcement)
- SQLite database in `nico_memory.db`

## Current Architecture

The project is split into modules (entry point is still `nico.py`):

- `config.py` - constants (wake words, DB path, Ollama settings, matching thresholds, voice
  settings, cloud API keys read from `.env` via `python-dotenv`, realtime-query keywords, graph edge
  threshold).
- `text_utils.py` - `normalize_text()`, `tokenize()`, `is_incomplete_command()`, `is_realtime_query()`,
  `strip_request_wrapper()` (strips a leading polite phrase like "can you"/"please" and reports
  whether the request was question-shaped - see "Follow-up round 10" below).
- `database.py` - `open_database()`, `create_table()`, `save_conversation()`, `fetch_all_conversations()`.
- `memory.py` - `find_conversation()` and the shared `keyword_score()` (Jaccard similarity), used both
  for cache lookup (`MemoryResult` with status `hit`/`ambiguous`/`miss`) and for building the memory
  graph's edges in `web_server.py`.
- `llm.py` - `ask_ollama()`, `build_context_prompt()`, `get_current_time()` (local Ollama only).
- `cloud_llm.py` - `ask_cloud_fallback()`: tries Groq, then Gemini, raises only if both fail.
- `web_search.py` - `search_web()` (Tavily) and `build_search_prompt()` to feed search results into a
  cloud LLM call.
- `documents.py` - `search_documents()` and `build_document_prompt()`: reads the daily research files
  from `config.DOCUMENTS_FOLDER` (see "Follow-up round 3" below) and scores them with
  `memory.keyword_score()`.
- `facts.py` - `search_facts()` and `build_facts_prompt()`: same approach as `documents.py`, but over
  the `facts` SQLite table (personal facts the user explicitly asked Nico to remember - see
  "Follow-up round 5" below).
- `reminders.py` - `parse_due_date()`, `maybe_schedule_reminder()`, `check_due_reminders()`,
  `reminder_loop()`: natural-language date/time parsing (`dateparser`) plus a background thread that
  fires due reminders via local speech (see "Follow-up round 7" and "Follow-up round 13" below).
- `system_control.py` - `open_target()`, `open_documentation()` (official URLs or browser search),
  `volume_up()`/`volume_down()`/`volume_mute()`, `take_screenshot()`, `get_battery_status()`
  (see "Follow-up round 9" below), `open_work_mode()` (see "Follow-up round 15" below).
- `weather.py` - `get_weather_report()`: free weather via Open-Meteo, no API key (see "Follow-up
  round 9" below).
- `research.py` - `run_research(topic, wanted, excluded)`: "modo pesquisa" - requires the topic,
  desired focus, and exclusions before searching the web (Tavily),
  asks the cloud (Groq/Gemini) to write a longer written report (not a short spoken reply), and
  saves an ABNT-inspired, timestamped `.pdf` with numbered source references to
  `config.RESEARCH_FOLDER` (see "Follow-up round 15" below).
- `calculator.py` - `calculate_spoken()`/`extract_expression()`: a safe (AST-based, no `eval()`)
  arithmetic calculator for spoken math like "quanto é 23 vezes 7" (see "Follow-up round 17" below).
- `wake_word.py` - `is_available()`/`listen_for_wake_word()`: optional 100%-local wake-word detection
  via Picovoice Porcupine, used instead of the cloud-based check in `voice.py` when configured (see
  "Follow-up round 17" below).
- `google_calendar.py` - `get_today_events()`: optional read-only Google Calendar integration via a
  private iCal feed URL (no OAuth app needed), merged into the agenda/briefing commands (see
  "Follow-up round 19" below).
- `commands.py` - `classify_command()`, `handle_command()`, `resolve_clarification()`; returns a
  `CommandResult` with kind `ANSWER`, `CLARIFY`, or `INCOMPLETE`. The internal `_get_llm_answer()`
  decides local vs. web-search-plus-cloud vs. cloud-as-reliability-fallback (see "Cloud reinforcement"
  below).
- `tts.py` - `speak()`: tries the neural voice (`edge-tts` + `pygame` playback) first, and falls back
  to the local `pyttsx3` voice if that fails (e.g. no internet).
- `state.py` - shared, thread-safe state: `conversation_history` (list) and `get_status()`/
  `set_status()`, read by the voice loop and the web server at the same time.
- `web_server.py` - Flask app (`run_web_server()`, static folder `web/`) serving:
  - `/` - the animated HUD (status orb, live transcript, text command box).
  - `/memory` - the memory galaxy (force-directed graph, click a node for the full Q&A, search box).
  - `/status`, `/history`, `/api/memory`, `/api/memory/graph`, `/command` (POST) - JSON endpoints
    backing the two pages; `/command` also lets a phone send typed commands without voice.
- `web/` - the actual HTML/CSS/JS: `index.html` + `hud.js` (HUD), `memory.html` + `galaxy.js` (galaxy
  graph, using vis-network from a CDN), `style.css` (shared dark/neon theme, Orbitron + Share Tech
  Mono fonts from Google Fonts).
- `desktop_app.py` - `open_desktop_window()`: waits for the Flask server to be reachable, then opens
  it in a pywebview native window (this *is* the GUI now - no separate Tkinter window).
- `voice.py` - `is_wake_word()`, `voice_cycle()`, `voice_loop()`; runs in a daemon thread started from
  `nico.py`. `voice_cycle()` uses `wake_word.is_available()` to pick between offline (Porcupine) and
  cloud (Google) wake-word detection each cycle (see "Follow-up round 17" below).
- `nico.py` - wires the modules together, starts the voice thread and the web server thread (port
  5000, listening on `0.0.0.0` so phones/tablets on the same Wi-Fi can reach it), prints the LAN URL
  to the console, then opens the pywebview window (blocking call, replaces the old `app.mainloop()`).

`state.conversation_history` is the single shared in-RAM history used by the voice loop and the web
server's `/command` endpoint (and shown in the HUD transcript).

### Cloud reinforcement logic (`commands._get_llm_answer`)

1. If the question looks time-sensitive (`is_realtime_query`, keyword list in `config.REALTIME_KEYWORDS`)
   and `TAVILY_API_KEY` is set: search the web (Tavily), then ask the cloud (Groq -> Gemini) to answer
   using those results.
2. Otherwise (or if that search/cloud call fails): ask the local Ollama model, as before.
3. If Ollama itself is unreachable (`requests.RequestException` - e.g. Ollama not running): try the
   cloud (Groq -> Gemini) as a reliability fallback, same as step 1's cloud call.
3. If literally everything fails: return a plain-English apology string instead of raising - the
   caller never needs to handle an exception from this function.

All API keys are optional and read from a local `.env` file (see `.env.example`); with none set, Nico
just behaves as it did before this round (local-only, no web search).

## Current Phase

All phases complete. Project status: finished.

- Phase 1-4 (initialization, basic voice loop, GUI, SQLite memory storage): done in earlier commits.
- Phase 5 (persistent memory): done. Memory lookup uses normalized keyword matching (Jaccard
  similarity over token sets) instead of exact string comparison. `handle_command()` handles
  incomplete commands (too short or ending in a dangling word like "and"/"but") and ambiguous
  matches (asks the user to clarify, then `resolve_clarification()` picks a candidate or falls back
  to a fresh Ollama call).
- Robustness pass: `voice_loop()` no longer dies on an unexpected exception (e.g. microphone
  disconnected) - it logs the error, updates the status label, and retries. Network/API failures from
  the speech recognition service (`sr.RequestException`) are caught alongside the existing
  `sr.UnknownValueError` / `sr.WaitTimeoutError` handling, instead of crashing the voice thread.

There is no planned next phase. If the user wants new features later, treat it as a fresh request,
not a continuation of a numbered phase.

### Follow-up round: voice, GUI, phone panel, memory browser (2026-09-30)

After using the finished project, the user asked for 7 adjustments. Done in this round:

1. Male voice - fixed (switched to neural voice, see `tts.py`).
2. Wake word occasionally misheard as "Nicole" - fixed (added aliases in `config.py`:
   nicole, nichole, nikolai, neeko, niku).
3. Robotic-sounding speech - fixed (same neural-voice switch as #1; the only two SAPI5 voices
   installed on this machine, Maria/pt-BR and Zira/en-US, were both flagged as robotic-sounding).
4. Interactive GUI (inspired by "Jarvis" style videos) - implemented a realistic, achievable version:
   an animated pulsing orb that changes color/speed by status, not a literal hologram.
5. Memory interface - implemented as a web page (`/memory`) with search, rather than a
   node/edge graph like `database-memory-mcp` (that remains a bigger future option if the user still
   wants a true graph view after trying this).
6. Calling the user's phone - **not implemented**. This needs a telephony service (e.g. Twilio,
   usually paid) or a companion phone app; a local Python script alone cannot place phone calls.
   Left as a future goal, pending the user picking/paying for a telephony provider.
7. Connecting phone/tablet - implemented a first step: a local Flask web panel reachable from any
   device on the same Wi-Fi (`http://<PC-LAN-IP>:5000`). Deeper OS-level integration (notifications,
   contacts, native app) is bigger, per-platform work and remains a future goal.

### Follow-up round 2: HUD interface, memory galaxy, cloud AI reinforcement (2026-09-30)

The user didn't like the plain orb GUI and asked for something more "technological," a memory
visualization closer to `database-memory-mcp`'s node graph ("like a mini galaxy"), and optional free
cloud AI APIs as backup for hard questions plus real web search for current info. Done:

- Replaced the Tkinter/CustomTkinter orb window with a pywebview window rendering an HTML/CSS/JS HUD
  (rotating rings, glowing pulsing core, terminal-style transcript) - see `desktop_app.py` and `web/`.
- Replaced the flat searchable memory list with an actual force-directed graph (`vis-network`),
  styled as a dark "galaxy" with glowing star-like nodes and faint connecting lines, sized/weighted by
  keyword similarity (reusing `memory.keyword_score`) - see `/memory`, `web/memory.html`, `web/galaxy.js`,
  and the `/api/memory/graph` endpoint in `web_server.py`.
- Added optional cloud reinforcement: Groq first, Gemini as its fallback (`cloud_llm.py`), used when
  Ollama is unreachable, and Tavily web search + cloud synthesis for time-sensitive questions
  (`web_search.py`). See "Cloud reinforcement logic" above. Free-tier API key sign-up links are in
  `.env.example`; the user has to create those accounts themselves.

### Follow-up round 3: response speed, and a daily research pipeline (2026-09-30)

The user asked for faster responses, and floated connecting a Google Drive folder of documents to
Nico - clarified to mean: a Claude *scheduled cloud routine* does daily research and saves it to
Drive, and Nico just reads what's already there (not Claude acting as Nico's live backend). Done:

- **Speed**: `tts.py` now caches every neural-voice audio clip to disk (`tts_cache/`, keyed by
  text+voice hash) - repeated fixed phrases (greetings, error messages, "could you finish that
  thought?", etc.) skip the edge-tts network call entirely after the first time. `llm.py`'s Ollama
  call now sets `num_predict` (caps generation length, `config.OLLAMA_NUM_PREDICT`) and `keep_alive`
  (`config.OLLAMA_KEEP_ALIVE`, keeps the model loaded in memory between calls instead of reloading it
  cold each time).
- **Daily research routine**: created a Claude scheduled cloud routine, "Nico Research - Daily Topics
  Sweep" (id `ROTINA-PRIVADA`, https://claude.ai/code/routines/ROTINA-PRIVADA),
  cron `0 10 * * *` (10:00 UTC = 07:00 America/Sao_Paulo, no DST in Brazil). Each day it researches
  Technology, Politics, Games, Anime, Manga, and Manhwa via web search, and writes ONE new file
  (`YYYY-MM-DD - Nico Research.txt`) into a "Nico Research" folder in the user's Google Drive, via the
  already-authorized Google Drive connector. Per the user's explicit instruction, it never deletes or
  overwrites anything - uncertain/single-source claims are marked inline as `[a revisar: ...]` instead
  of being dropped.
- **Nico reads those documents**: new `documents.py` - `search_documents()` scans the most recent
  files in `config.DOCUMENTS_FOLDER` (a local path, set once the user installs Google Drive Desktop
  and it syncs the "Nico Research" folder to their machine) and scores sections by the same
  `memory.keyword_score()` used elsewhere; `build_document_prompt()` feeds relevant matches to the
  local Ollama model. This is now the *first* thing `commands._get_llm_answer()` tries (free, local,
  no network), before the realtime-search/cloud path and the plain local-Ollama path.
- `DOCUMENTS_FOLDER` is empty by default (read from `.env`) - until the user sets it up, Nico just
  skips this step, same as the other optional integrations.

### Follow-up round 4: real API keys, multi-folder docs, .docx support, galaxy starfield (2026-09-30)

- The user pasted real Groq/Gemini/Tavily keys into chat; they were written straight to the local
  `.env` (never echoed back, never committed). Live-tested all three: `GROQ_MODEL` and `GEMINI_MODEL`
  had to be updated (`llama-3.3-70b-versatile` and `gemini-2.0-flash` were both decommissioned) to
  `openai/gpt-oss-120b` and `gemini-3.8-flash` - confirmed working end to end, including the
  Groq-then-Gemini fallback chain and a real Tavily search.
- Google Drive Desktop is now installed and syncing to `G:\Meu Drive`. `DOCUMENTS_FOLDER` is set to
  `G:\Meu Drive\Nico Research` (created empty ahead of the routine's first run, to avoid any
  find-or-create ambiguity on day one).
- Added a second folder, `NOTES_FOLDER` (`G:\Meu Drive\Nico Notes`), for the user's own manual notes -
  `config.DOCUMENT_FOLDERS` is now a list combining both, and `documents.py` scans all of them. An
  `exemplo.txt` was left in `Nico Notes` showing the expected format (blank-line-separated sections).
- `documents.py` reads `.txt`, `.md`, `.docx` (via `python-docx`), and `.pdf` (via `pypdf`) from
  configured document folders. PDF pages are extracted as searchable text. No folder is pointed at
  `.docx` content yet (e.g. the user's "Cursos" folder) - that's opt-in, add it to `.env` as a third
  `DOCUMENT_FOLDERS` entry if wanted.
- `web/memory.html` + new `web/starfield.js`: replaced the static CSS-dot background on the memory
  galaxy page with a real animated starfield (tsParticles, free CDN), layered behind the vis-network
  canvas (`#starfield` z-index 0, `#galaxy` z-index 1, transparent background on the graph layer).

### Follow-up round 5: gitignore fix, and a real "remember" capability (2026-09-30)

- Caught and fixed a typo in `.gitignore` (`.envc` instead of `.env`, introduced by an edit outside
  this session) that would have let the real `.env` - containing live Groq/Gemini/Tavily keys - be
  picked up by `git add`. Confirmed via `git log --all -- .env` that it was never actually committed.
  **Always double-check `.gitignore` still covers `.env` exactly if it shows as changed.**
- Diagnosed a real bug report: the user said "I have a test this Friday can you remember me" and got
  a stale cached "Good luck!" answer from an unrelated earlier conversation. Root cause: two things
  compounding -
  1. Whatever process the user had running was likely started before some of this session's earlier
     edits (recomputing the Jaccard score with the *current* code gives 0.545, below
     `MATCH_THRESHOLD` - so current code would have said "miss", not "hit"). **Lesson: after code
     changes, the user needs to restart `nico.py` - it does not hot-reload.**
  2. Deeper gap: Nico had no real "remember a fact" capability. "Remember" was only ever being
     treated as a regular question, matched against the Q&A cache by keyword overlap - which is
     fragile for short, generic phrasings about the same topic.
- Added a genuine remember/recall feature:
  - New `facts` table (`database.py`: `save_fact()`, `fetch_all_facts()`).
  - `classify_command()` now recognizes an explicit `REMEMBER` intent (trigger phrases in
    `config.REMEMBER_TRIGGERS`: "remember", "remind me", "don't forget", "note that"), while
    `config.REMEMBER_RECALL_PREFIXES` ("do you remember", "what do you remember", ...) is checked
    first so recall questions still fall through to the LLM path instead of being mis-stored as a
    new fact.
  - `handle_command()` on `REMEMBER` just calls `save_fact()` and replies "Got it, I'll remember
    that." - it no longer goes anywhere near the Q&A cache.
  - New `facts.py` (`search_facts()`, `build_facts_prompt()`, same `keyword_score()`-based approach
    as `documents.py`) is now the *first* source `commands._get_llm_answer()` tries - ahead of
    research documents, web search, and plain Ollama - since a fact the user explicitly asked to be
    remembered is the most relevant thing to check first.

### Follow-up round 6: Telegram notifications via CallMeBot (2026-09-30)

The user has a CallMeBot Telegram integration already authorized (their Telegram username, no API
key needed - CallMeBot's free tier). Added:

- `notify.py` - `send_telegram_message(text)`: a simple GET to CallMeBot's `text.php` endpoint
  (`config.TELEGRAM_API_URL`), using `config.TELEGRAM_USER` (from `.env`, no key required). Raises if
  `TELEGRAM_USER` is empty, the request fails, or CallMeBot doesn't confirm `"Status: Successful"`.
- New `NOTIFY` intent in `classify_command()` (`config.NOTIFY_TRIGGERS`: "text my phone", "message my
  phone", "notify my phone", "send me a message"). `handle_command()` extracts whatever text follows
  the trigger phrase as the message body (falls back to a generic line if there's nothing after it),
  sends it via `notify.send_telegram_message()`, and reports success/failure back to the user by
  voice - this never touches the Q&A cache or the LLM.
- Reliability alert: in `_get_llm_answer()`, if *both* the local Ollama model and the Groq/Gemini
  cloud fallback fail, and `TELEGRAM_USER` is configured, Nico best-effort sends itself a Telegram
  message saying it's down, before returning the usual spoken apology.
- This is a free, unofficial, best-effort channel (not affiliated with Telegram/WhatsApp) - fine for
  personal notifications, not for anything that must be delivered reliably.
- The `telegram-call-api` (an actual voice call reading a message aloud, not just a text) was
  discussed as an option but not implemented - `text.php` (silent text message) is what got wired up.
  Timed reminders (below) reuse this same text-message channel, not a voice call.

### Follow-up round 7: real scheduled/timed reminders (2026-09-30)

Implemented the piece explicitly deferred in round 6: "remember I have a test Friday at 2pm" now
actually schedules something that fires at the right time, instead of only being a searchable fact.

- New `reminders` SQLite table (`database.py`: `save_reminder()`, `fetch_due_reminders()`,
  `mark_reminder_notified()` - `due_at` stored as a UTC ISO timestamp, `notified` flag to avoid firing
  twice).
- `reminders.py` - `parse_due_date(text)` uses `dateparser.search.search_dates` (free, fully offline,
  no API key) with `PREFER_DATES_FROM: "future"` and `TIMEZONE: config.REMINDER_TIMEZONE`
  (`America/Sao_Paulo`). Two real `dateparser` quirks were found and guarded against during testing:
  1. A bare time with no am/pm/colon (e.g. "at 5") can get parsed using the *current* time-of-day
     instead of a real hour - detected by checking whether the matched text fragment contains an
     explicit time marker (`am`/`pm`/`:`/`noon`/`morning`/etc., or a relative-duration phrase like
     "in 2 hours"); if not, the time is overridden to `config.REMINDER_DEFAULT_HOUR` (09:00 local).
  2. A bare time with literally no date context (e.g. "at 5pm" with nothing else) can resolve to a
     nonsensical date over a month in the past. Guard: if the final UTC datetime is still in the past
     even after rolling forward by one day (for the ordinary "that time already passed today" case),
     `parse_due_date` returns `None` - no reminder is scheduled - rather than risk firing at the wrong
     moment. **Lesson: never trust a single natural-language date parse without a past/future sanity
     check; silently not scheduling is safer than scheduling wrong.**
  3. `maybe_schedule_reminder(command_text)` is what `handle_command()` calls on `REMEMBER` - it saves
     the fact either way, and additionally schedules a reminder (plus returns a spoken confirmation
     of when) only if `parse_due_date` found something it trusts.
  - `check_due_reminders()` / `reminder_loop()`: a background daemon thread (started in `nico.py`
    alongside the voice and web threads) polls every `config.REMINDER_CHECK_INTERVAL_SECONDS` (30s)
    for due, not-yet-notified reminders, and for each one both sends a Telegram message
    (`notify.send_telegram_message`) and speaks it out loud locally (`tts.speak`) - independent
    try/except around each, so one channel failing doesn't block the other or crash the loop.
- Known limitation: a date mentioned incidentally in a fact that wasn't meant as a reminder (e.g.
  "remember my birthday is in December") will still schedule a reminder, since there's no attempt to
  distinguish "this fact happens to contain a date" from "please alert me at this date" - that would
  need deeper intent classification than this project currently has.

### Follow-up round 8: desktop shortcut (2026-09-30)

- `Iniciar Nico.bat` (project root): `cd`s into the project folder, then runs
  `start "Nico" /min py -3.11 nico.py` - a minimized console window, titled "Nico", in the right
  working directory (needed since `DB_PATH`, `tts_cache/`, etc. are relative paths).
- A desktop shortcut ("Nico.lnk") was created pointing at that `.bat`. The user's actual Desktop
  folder is OneDrive-redirected to `C:\Users\usuario\OneDrive\Área de Trabalho` (same parent folder as
  the project itself), not the default `C:\Users\usuario\Desktop` - confirmed via
  `[Environment]::GetFolderPath("Desktop")` before creating the shortcut, rather than assuming.
  **Lesson: never assume the Desktop/Documents/etc. path on this machine - OneDrive folder
  redirection means the real path can differ from the Windows default.**
- Tested end-to-end: launching the `.bat` starts the `python3.11` process and the web panel responds
  on `http://127.0.0.1:5000/`. Note for future testing: invoking the `.bat`/`start` command through
  Git Bash's `cmd.exe` with nested quotes was unreliable (the process silently failed to launch) -
  PowerShell's `Start-Process` is the reliable way to test a Windows shortcut/batch file from this
  environment.
- Auto-start on boot was discussed, then explicitly declined by the user ("não vamos iniciá-lo junto
  com meu notebook, mudei essa ideia") - only the desktop icon stands; do not add a Startup-folder
  shortcut unless they ask again.
- Follow-up: the user wanted a nicer icon than the default `.bat` one. `scripts/make_icon.py` (a
  one-off utility script, not part of the running app) generates `nico_icon.ico` with Pillow - a
  glowing cyan/purple orb matching the HUD's color scheme, rendered at the sizes Windows actually
  uses (16/24/32/48/64/128/256) so it stays crisp at every icon size. The desktop shortcut's
  `IconLocation` now points at it. Re-run `py -3.11 scripts/make_icon.py` to regenerate if the HUD's
  color scheme ever changes and the icon should follow.

### Follow-up round 9: classic "Jarvis" features (2026-10-01)

The user asked to look at what common open-source "Jarvis" voice-assistant projects do and adopt
what makes sense now. Implemented the safe, reversible, high-value ones; explicitly skipped anything
destructive (shutdown/restart/lock screen) since those interrupt the user's session and the project's
Safety rules require explicit confirmation before destructive actions - that would need a
confirmation flow this project doesn't have yet.

- `system_control.py`:
  - `open_target(name)` - "open chrome", "open youtube", etc. Checks `config.APP_SHORTCUTS` (Windows
    apps, via `subprocess.Popen`/`os.startfile`) then `config.SITE_SHORTCUTS` (websites, via
    `webbrowser.open`), and falls back to a Google search for anything unrecognized - so it never
    just fails silently on an unknown name.
  - `volume_up()` / `volume_down()` / `volume_mute()` - pure `ctypes` calls to
    `user32.keybd_event` with the Windows volume virtual-key codes. No extra dependency needed (no
    `pycaw`, no `keyboard` package) - this is the simplest free way to do it on Windows.
  - `take_screenshot()` - `PIL.ImageGrab.grab()` (Pillow, already a dependency for the desktop icon),
    saved with a timestamp into `config.SCREENSHOT_FOLDER` (`screenshots/`, gitignored).
  - `get_battery_status()` - `psutil.sensors_battery()`; reports gracefully ("doesn't report a
    battery") on a desktop PC with no battery.
- `weather.py` - `get_weather_report()`: real weather via Open-Meteo (`api.open-meteo.com`, free, no
  API key, no signup) instead of relying on the generic Tavily-search-plus-cloud-LLM path for this
  one very common question. Uses `config.WEATHER_CITY` if set, otherwise auto-detects the city via
  free IP geolocation (`ip-api.com`). On any failure, `commands.py` falls back to the normal
  realtime-search path rather than erroring out (the "WEATHER_TRIGGERS" check happens before the
  existing "weather" entry in `REALTIME_KEYWORDS`, so that path still exists as a safety net).
- New intents in `classify_command()`/`handle_command()`: `OPEN` (`config.OPEN_PREFIX = "open "`),
  `VOLUME_UP`/`VOLUME_DOWN`/`VOLUME_MUTE`, `SCREENSHOT`, `BATTERY`, `WEATHER` - all checked before the
  generic `LLM` fallback, same pattern as every other intent in this file.
- Deliberately NOT added: shutdown/restart/sleep/lock-screen voice commands, and Spotify/music
  playback control (needs OAuth). Both remain candidates if the user asks for them specifically, with
  a confirmation step required for anything destructive.

### Follow-up round 10: polite phrasing, typo tolerance, social media shortcuts (2026-10-01)

Two real problems surfaced from actual use: "can you open my instagram" didn't match the `OPEN`
intent at all (it only matched a bare `"open "` prefix), and the user wanted Nico to sound more
natural - acknowledging a question-phrased request ("can you...?") differently from a direct order
("open...").

- `config.SITE_SHORTCUTS` gained Instagram, Facebook, TikTok, LinkedIn, Discord, Telegram, Twitch,
  Pinterest - "open <social network>" just opens it in the browser. (Deep API access - reading
  notifications, posting, etc. - was explicitly explained to the user as not feasible the same way
  Groq/Tavily/Drive were: official platform APIs are locked down against this kind of automation and
  require developer/business review, and unofficial scraping-style automation risks the account being
  banned - this was a deliberate explanation, not an oversight, and nothing of that kind was built.)
- `text_utils.strip_request_wrapper(text)` - new general-purpose helper, used at the very top of
  `handle_command()` (`core_text, was_question = strip_request_wrapper(command_text)`), and `core_text`
  is what every classification/trigger check and downstream action now uses (previously it was
  `command_text` throughout). It strips a leading polite phrase ("can you", "could you please",
  "would you", "will you", "please") and reports whether the original looked like a question
  (started with "can/could/would/will you"). This is the actual fix for the "can you open..." bug -
  it's a general fix, not OPEN-specific, so it also helps every other trigger-based intent
  (`NOTIFY`, `VOLUME_*`, `SCREENSHOT`, `REMEMBER`, etc.) recognize politely-phrased requests.
  `REMEMBER_RECALL_PREFIXES` ("do you remember...") is unaffected since "do you" isn't in the
  stripped-prefix list - recall questions still correctly fall through to the LLM path.
- `commands._affirm(message, was_question)`: when the original request was question-shaped, prefixes
  the action's response with "Sure, " (lowercasing the next word) - e.g. "can you mute?" -> "Sure,
  muted."; a direct "mute" -> just "Muted." This is applied to `OPEN`, `NOTIFY`, `VOLUME_*`, and
  `SCREENSHOT` (the "do something" intents) - not to `BATTERY`/`WEATHER`/`TIME` etc., which are
  informational answers rather than actions, so the distinction doesn't apply there.
- `system_control.open_target()` is now typo-tolerant: speech-to-text mishearings like "instragram"
  for "instagram" are matched via `difflib.get_close_matches` (cutoff 0.75) against the known
  `APP_SHORTCUTS`/`SITE_SHORTCUTS` names, after first stripping filler words a spoken request tends
  to include ("my", "the", "a", "an", "may" - "may" specifically because STT sometimes mishears "my"
  as "may", "please"). Falls back to the previous behavior (try as a bare URL, then Google search) if
  nothing is close enough.

### Follow-up round 11: volume-up trigger fix (2026-10-01)

Real bug the user hit right after round 10: "it lowers my volume but isn't increasing it." Root
cause - `VOLUME_UP_TRIGGERS`/`VOLUME_DOWN_TRIGGERS` were fixed exact phrases ("turn up the volume",
"increase the volume"), so natural variations like "increase my volume" or "turn my volume up"
(different word order / "my" instead of "the") never matched, while whatever down-phrasing the user
happened to use apparently matched one of the fixed down-phrases by luck.

- Replaced both with **word-set matching**: `config.VOLUME_UP_WORDS`/`VOLUME_DOWN_WORDS`/
  `VOLUME_MUTE_WORDS` are sets of individual direction words (up/higher/increase/louder/raise/more,
  down/lower/decrease/quieter/reduce/less, mute/silence/...). `classify_command()` now checks: if the
  normalized text contains "volume" anywhere **and** shares any word with the matching direction set
  (word order doesn't matter), classify accordingly. "louder"/"quieter" alone (without the word
  "volume") still work as a fallback, same as before.
- **Lesson for any future trigger-phrase list in this project: prefer "keyword(s) present anywhere in
  the sentence" over "this exact phrase substring" whenever the phrasing is something a person would
  naturally say several different ways. Exact-phrase triggers look like they work in testing (because
  the tester tends to type the same phrasing used to write the trigger) but silently miss real speech
  variation - which is exactly what happened here and in round 10's "can you open" bug.**

### Follow-up round 12: "call me" via Telegram voice call (2026-10-01)

A real phone call through a carrier still needs a paid telephony service (Twilio etc.) and remains a
future goal (see below). But CallMeBot - already authorized for the "text my phone" feature - also
offers a free voice-call API: it calls the user inside the Telegram app itself and reads a message
aloud via text-to-speech. Since this reuses the *same* authorization the user already did (the
one-time `/start` to `@CallMeBot_txtbot`), no new setup was needed.

- `notify.make_telegram_call(text=None)` - GET to CallMeBot's `start.php` (`config.TELEGRAM_CALL_API_URL`),
  same `TELEGRAM_USER` as the text feature. Caps the message at 256 characters (CallMeBot's limit) and
  repeats it twice (`rpt=2`). Raises if `TELEGRAM_USER` is empty or the request fails - same pattern as
  `send_telegram_message`.
- New `CALL` intent in `classify_command()` (`config.CALL_TRIGGERS`: "call me", "phone me", "give me a
  call", "call my phone") and `commands._call_phone()` in `handle_command()`, following the exact same
  shape as the `NOTIFY`/`_send_phone_notification()` pair, including the `_affirm()` question/order
  distinction from round 10 ("can you call me?" -> "Sure, calling you now."; "call me" -> "Calling you
  now - check your Telegram.").
- This is a Telegram voice call, not a real telephone call through the carrier - worth keeping in mind
  since the user's phone doesn't ring as a normal call, it rings inside Telegram.

**Superseded by round 13 below**: CallMeBot turned out to require payment (their free tier stopped
being usable for this), so the user asked to remove it entirely - this includes the `CALL` feature
just described, and the pre-existing `NOTIFY` feature and down-alert from round 6.

### Follow-up round 13: removed CallMeBot/Telegram entirely (2026-10-01)

Right after round 12 shipped, CallMeBot started asking for payment, so the user said to drop
everything tied to it - not just the brand-new `CALL` feature, but the older `NOTIFY` ("text my
phone...") feature and the Ollama/cloud down-alert from round 6 as well, since all three depended on
the same CallMeBot account.

- Deleted `notify.py` entirely (`send_telegram_message()`, `make_telegram_call()`).
- `commands.py`: removed the `NOTIFY` and `CALL` intents from `classify_command()`, the
  `_send_phone_notification()`/`_call_phone()` helpers, their branches in `handle_command()`, and the
  Telegram down-alert block in `_get_llm_answer()` (both local Ollama and cloud failing now just
  returns the apology string, with nothing sent anywhere).
- `config.py`: removed `TELEGRAM_USER`, `TELEGRAM_API_URL`, `TELEGRAM_CALL_API_URL`,
  `NOTIFY_TRIGGERS`, `CALL_TRIGGERS`. `SITE_SHORTCUTS["telegram"]` (just opens web.telegram.org in a
  browser) was kept - that's unrelated to the CallMeBot API, it's the same kind of "open <site>"
  shortcut as any other social link.
- `reminders.py`: `check_due_reminders()` no longer sends a Telegram message when a reminder fires -
  it only speaks it out loud locally now (`tts.speak`). Timed reminders still work, just through one
  channel instead of two.
- `.env`/`.env.example`: removed `TELEGRAM_USER`.
- **Lesson: before wiring up a "free" third-party API as a real feature, be ready for it to start
  gating behind payment later - this is the second time in this project a free-tier assumption needed
  walking back (the Groq/Gemini model-deprecation issue in round 4 was the first). Nothing stops this
  from being revisited with a different provider later if the user wants phone notifications/calls
  again.**

### Follow-up round 14: full switch to Portuguese + Jarvis-style personality (2026-10-02)

The user asked for the whole project to speak Portuguese, and for Nico's personality to be calm,
friendly, a little gentlemanly, and close to how Jarvis talks. This touched speech recognition, the
TTS voice, every trigger phrase, every hardcoded spoken/written reply, every LLM system prompt, the
web UI text, and the reminder date parser. Python identifiers, function names, and code comments
were deliberately left as they already were (a mix of English identifiers with mostly-Portuguese
comments, as this project has used throughout) - translating those would be a large mechanical
rename with no behavior benefit; "the project" here means what Nico says and understands.

- **Voice in/out**: `voice.py`'s `recognize_google(..., language=...)` changed from `en-US` to
  `pt-BR`. `tts.py`'s neural voice (`config.NEURAL_VOICE`) changed to `pt-BR-AntonioNeural` - checked
  live via `edge_tts.list_voices()` that it exists and is male (it's currently the *only* male pt-BR
  voice edge-tts offers). The local pyttsx3 fallback (`config.VOICE_INDEX`) switched from index 1
  (Zira, en-US) to index 0 (Maria, pt-BR), so even the offline fallback speaks the right language.
- **Accent-insensitive matching**: `text_utils.normalize_text()` now strips accents (NFD decompose +
  drop combining marks) before comparing, so "não"/"nao", "é"/"e", "às"/"as" etc. all match the same
  trigger regardless of exactly how the speech recognizer transcribes accents. Every trigger constant
  in `config.py` is written without accents accordingly. This also fixed a bug *introduced* by this
  same change and caught before shipping: `WAKE_WORDS` had an accented `"nicolò"` entry that would
  have stopped matching once accent-folding was added - removed as a duplicate of the existing
  unaccented `"nicolo"` entry.
- **Every trigger phrase rewritten for natural Portuguese**, following the round 11 lesson (prefer
  loose keyword matching over exact phrases): `REMEMBER_TRIGGERS` ("lembre", "lembra", "lembre que",
  "me lembre de", "não esqueça", ...), `REMEMBER_RECALL_PREFIXES` ("você lembra", ...),
  `OPEN_PREFIXES` (now a tuple - "abra "/"abrir "/"abre ", replacing the old single `OPEN_PREFIX`),
  `VOLUME_KEYWORDS`/`VOLUME_UP_WORDS`/`VOLUME_DOWN_WORDS`/`VOLUME_MUTE_WORDS` ("volume"/"som" +
  aumenta/sobe/mais or diminui/abaixa/menos or mudo/silêncio, any order), `SCREENSHOT_TRIGGERS`,
  `WEATHER_TRIGGERS`, `REALTIME_KEYWORDS`, `INCOMPLETE_TRAILING_WORDS`. `BATTERY_TRIGGERS` was
  simplified to just `("bateria",)` - a single loose keyword, same reasoning as round 11.
  `APP_SHORTCUTS`/`SITE_SHORTCUTS` gained Portuguese aliases alongside the existing English/proper-noun
  names (e.g. "calculadora" next to "calculator", "configuracoes" next to "settings") since people
  say both; `system_control._FILLER_WORDS` changed from English filler words to Portuguese articles/
  possessives ("o", "a", "meu", "minha", ...).
- **Every hardcoded reply rewritten in Portuguese** with the calm/friendly/gentlemanly tone, across
  `commands.py` (greetings, time, mood, thanks, capabilities, identity, remember confirmation, volume/
  screenshot/battery/weather replies, the ambiguous-memory clarification question, the final "both
  Ollama and cloud failed" apology), `system_control.py` (opening apps/sites, Google-search fallback,
  battery status), `weather.py` (the weather sentence itself and all WMO weather-code descriptions,
  e.g. "céu limpo", "chuva forte"). `commands._affirm()`'s question-vs-order prefix changed from
  "Sure, " to "Claro, ", keeping the exact same mechanism from round 10.
- **LLM personality**: the system prompts in `llm.py` (local Ollama) and `cloud_llm.py` (Groq/Gemini
  fallback) were rewritten to explicitly describe the Jarvis-inspired calm/friendly/gentlemanly
  personality and instruct the model to answer in Brazilian Portuguese, with updated few-shot
  examples. `build_context_prompt()`'s conversation-history labels changed from "User:"/"Assistant:"
  to "Usuário:"/"Nico:". The prompt-building helpers in `web_search.py`, `documents.py`, and
  `facts.py` were likewise rewritten to ask for Portuguese answers. `llm.get_current_time()` switched
  from a 12-hour `AM/PM` format to 24-hour (`%H:%M`), which is how time is normally said in Brazil.
- **Reminder date parsing - a real `dateparser` bug found and fixed**: testing surfaced that
  `dateparser`'s Portuguese (`pt`) locale badly misreads a weekday name combined with a numeric hour -
  e.g. `"sexta-feira às 14h"` was parsed as *the 14th day of the month* at `00:00`, completely
  discarding "sexta-feira" and misreading "14h" as a day-of-month instead of an hour. The same
  happened with `"amanhã às 9h"` (wrong day *and* wrong hour). This reproduced consistently across
  several phrasings, confirmed by inspecting `dateparser.search.search_dates()`'s raw output
  directly - it's a locale limitation in the library itself, not a bug in this project's old logic.
  Fix: `reminders.py` now extracts an explicit time phrase (`"às 14h"`, `"as 9 horas"`, with optional
  "da manhã"/"da tarde"/"da noite") with a dedicated regex (`_extract_explicit_time`) *before* handing
  the text to `dateparser`, strips that phrase out, and applies the extracted hour/minute manually
  after `dateparser` resolves the date-only remainder (which it does correctly on its own, e.g. just
  `"sexta-feira"` or `"amanhã"`). Verified with several real phrasings after the fix, all correct
  (right weekday *and* right hour). Reminder date/time formatting also no longer depends on
  `strftime("%A, %b %d")` (which would print English weekday/month names on this machine, since no
  pt-BR locale is installed system-wide) - `reminders._format_local_pt()` builds the Portuguese
  weekday/month names from two small lookup tuples instead, and uses 24-hour time.
  **Lesson: don't trust a natural-language date library's locale support for anything beyond the
  date itself without testing combined date+time phrasings specifically - locale quality for time
  expressions can lag badly behind date expressions in the same library.**
- **Web UI**: `web/index.html`, `web/memory.html`, `web/hud.js`, `web/galaxy.js` - all visible text
  (placeholders, buttons, links, status words, the "You:"/"Nico:" transcript labels) translated to
  Portuguese. The status words Nico reports while running (`state.py`'s default, and every
  `set_status(...)` call in `voice.py`/`tts.py`) changed to Portuguese ("Ouvindo", "Pensando",
  "Falando", "Erro - tentando novamente") and `hud.js`'s `STATUS_COLORS` map / error-prefix check
  updated to match, so the HUD's color-coding still works correctly with the new words.
- Verified end-to-end after all changes: full `py_compile` across every module, a battery of
  `classify_command()` tests across ~20 natural Portuguese phrasings (greetings, time, mood, thanks,
  capabilities, identity, remember, open, volume up/down/mute, screenshot, battery, weather - all
  correct), a real `handle_command()` smoke test (including an actual screenshot and a real TTS
  synthesis + playback through the new `pt-BR-AntonioNeural` voice), and the reminder date-parsing
  fix re-tested with 5 phrasings after the regex fix (all correct).

### Follow-up round 15: Edge "work mode" + a real research ("modo sério") mode (2026-10-02)

The user asked for two new "Nico actually touches my computer" features: a work mode that opens a
specific Edge Workspace, and a research mode where Nico searches a topic and saves a report to a
file (optionally on Drive).

- **Work mode** (`"modo trabalho"`, `"modo estudos"`, etc.) - ended up **not** using Edge's native
  Workspaces feature at all, after a dead end investigating it directly:
  - First tried `msedge --launch-workspace="<id>"` (a real but undocumented CLI flag) plus a
    `WorkspacesCache` JSON file supposedly holding workspace IDs locally - neither worked on this
    machine. The user's six Workspaces (Estudos, Trabalho, Faculdade, Leitura, Programação,
    Entretenimento) are synced via their Microsoft account and only live in Edge's internal `Sync
    Data` LevelDB store; that cache file never got created even after opening a workspace. Attempting
    to grep/strings that LevelDB file for an ID was correctly blocked by the auto-mode safety
    classifier as "credential exploration" (that store sits right next to session/sync credentials) -
    this was not worked around, in line with the project's safety rules.
  - Then tried Edge's "Copy link" (Workspaces -> Invite -> Copy link) as a safe, fully-supported
    alternative that needs no internal file parsing - but it turned out this collaboration/sharing
    feature was **removed in current Edge versions (144+)**; the user is on 154, so the menu item the
    docs described simply isn't there anymore. Confirmed via Microsoft's own support page before
    telling the user to stop looking for something that doesn't exist in their version.
  - **Also worth noting for future reference**: mid-investigation, the user's Workspaces briefly
    disappeared entirely from Edge, then came back on their own shortly after. The Edge Workspaces
    logs show an internal "Spaceworks" migration subsystem; this looks like a transient Edge-side sync
    glitch, unrelated to anything run in this session (every action taken against Edge's data in this
    session was read-only - `find`/`cat` on log files - and the one LevelDB read attempt was blocked
    before it ran). Flagged to the user as reassurance, not left ambiguous.
  - **Final approach**: skip native Edge Workspaces entirely. `config.WORK_MODES` is built generically
    from any `.env` variable named `WORK_MODE_<NAME>` holding a comma-separated list (e.g.
    `WORK_MODE_TRABALHO=gmail,github,https://meusite.com`) - each item is anything `open_target()`
    already understands (an `APP_SHORTCUTS`/`SITE_SHORTCUTS` name, or a bare URL). `system_control.
    open_work_mode(name)` just calls `open_target()` once per configured item, or lists the configured
    mode names if the spoken one isn't found. This is less visually tied to Edge's own Workspaces UI,
    but far more robust (no dependency on an Edge feature that changes or vanishes between versions)
    and more flexible (can mix apps and sites, isn't Edge-specific at all).
  - `classify_command()` recognizes `WORK_MODE` whenever the word "modo" appears anywhere in the
    sentence (not just as a prefix) - so "modo trabalho", "ativar o modo trabalho", and "entra no modo
    estudos" all work; the mode name is everything after that word.
  - **Lesson: verify a platform feature still exists in the *installed* version before designing
    around its documented behavior - "Copy link" was real, just not anymore, and checking the actual
    Edge version against Microsoft's own changelog-style support page caught this before any more time
    was sunk into it.**
- **Research ("modo sério") mode** (`"pesquise sobre X"`, `"pesquisa sobre X"`): new `research.py` -
  `run_research(topic)` searches the web via the existing `web_search.search_web()` (Tavily, same as
  the realtime-query path), then asks the cloud (`cloud_llm.ask_cloud_fallback()`) to write a longer,
  structured *written* report - not a short spoken reply - grounded only in the search results. This
  needed `cloud_llm.ask_groq()`/`ask_gemini()`/`ask_cloud_fallback()` to accept an optional
  `system_prompt` override (default stays the short-spoken-reply personality prompt used everywhere
  else), since a saved report needs different instructions than a voice answer. The report is saved as
  a timestamped, ABNT-inspired `.docx` file in `config.RESEARCH_FOLDER` (defaults to `NOTES_FOLDER` if that's
  configured, so `documents.py` picks the report up automatically for future questions too - a nice
  side effect of reusing the same folder - otherwise falls back to a local `pesquisas/` folder,
  gitignored like `screenshots/`). New `RESEARCH` intent in `classify_command()`
  (`config.RESEARCH_TRIGGERS`: "pesquise sobre", "pesquisa sobre", "faça uma pesquisa sobre", "pesquise
  a fundo sobre") and `commands._run_research()`/`_extract_after_trigger()` (a small generalized
  version of the old `NOTIFY`-era text-after-trigger extraction) in `handle_command()`. This call can
  take noticeably longer than a normal question (web search + a full report generation) - it still
  runs synchronously like every other LLM call in this project (no background-job system exists yet),
  so the user just waits for the spoken confirmation once the file is saved.
- Verified: full `py_compile`, and `classify_command()`/`handle_command()` tests for both features
  (work mode correctly reports "not configured yet" with no `.env` entries present, in several
  phrasings; research intent and topic extraction tested separately from the network calls).

### Follow-up round 16: timer and "today's agenda" (2026-10-05)

The user asked to research what else could be added to the project. Looked at current (2026)
open-source Jarvis-style assistant projects for ideas (offline wake-word detection, faster-whisper,
LLM tool-calling, modular skills, timers) and picked the two that were low-risk, clearly useful, and
could reuse the existing `reminders` table/background loop instead of adding new machinery:

- **Timer** (`"timer de 10 minutos"`, `"cronômetro de 30 segundos"`): `reminders.schedule_timer()`
  pulls a `quantity + unit` out of the spoken text with a small regex
  (`\d+\s*(segundos?|minutos?|horas?)\b` - the `?` suffix form instead of listing both singular and
  plural alternatives avoids a real regex bug caught during testing: an alternation written as
  `segundo|segundos` matches the shorter `"segundo"` first inside `"segundos"`, silently dropping the
  trailing "s" and producing "10 minuto" instead of "10 minutos"), then builds `"em {quantity}
  {unit}"` and feeds it straight into the *already-proven* `parse_due_date()` relative-duration path
  (same one that correctly handles "me lembre em 2 horas") instead of writing new date math. Saves a
  normal row in the existing `reminders` table via `database.save_reminder()`, so it fires through the
  same `reminder_loop()` that already exists - no new background thread, no new table.
  `config.TIMER_TRIGGERS = ("timer", "cronometro", "alarme")`.
- **Today's agenda** (`"o que eu tenho hoje"`, `"minha agenda"`): new `database.
  fetch_reminders_between(start_iso, end_iso)` plus `reminders.get_today_agenda()`, which computes
  today's local midnight-to-midnight window, converts it to UTC for the query, and returns each
  reminder as `"HH:MM - texto"`. `config.AGENDA_TRIGGERS`. Shows both past and future reminders for
  the day (not just pending ones) since the user is asking "what do I have today," not "what's still
  coming."
- Verified: full `py_compile`, `handle_command()` tests for both (including re-testing the timer
  phrasing after the regex fix), and cleaned up the test timer rows from `nico_memory.db` afterward so
  they wouldn't fire as real spoken alerts the next time `nico.py` actually runs.
- **Other ideas surfaced but not built, left for the user to request if wanted**: offline wake-word
  detection (e.g. openWakeWord/pvporcupine) so Nico doesn't need a network round-trip to Google just to
  notice its own name - a real latency/privacy win, but a bigger change to `voice.py`'s core loop and a
  new dependency, so it needs its own go-ahead; a dedicated safe-arithmetic calculator intent ("quanto
  é 23 vezes 7") instead of relying on the LLM for math; a combined "bom dia" briefing (weather + 
  today's agenda in one spoken summary).

### Follow-up round 17: calculator, "bom dia" briefing, and offline wake-word detection (2026-10-05)

Right after round 16, the user asked to implement all three ideas that had been left as suggestions.

- **Calculator** (`"quanto é 23 vezes 7"`, `"calcule 100 dividido por 4"`): new `calculator.py` -
  `extract_expression()` converts spoken Portuguese math words ("mais"/"menos"/"vezes"/
  "multiplicado"/"dividido"/"elevado", with "dividido por"/"multiplicado por" collapsing the "por"
  into the operator) into a plain arithmetic expression string, and `safe_eval()` evaluates it by
  walking a restricted `ast` tree (only numeric constants and `+ - * / ** %` nodes are allowed) instead
  of calling Python's `eval()` - which would otherwise execute arbitrary code from speech-recognized
  text, a real injection risk this project explicitly avoids (see the `AGENTS.md` Safety section's
  "no arbitrary SQL" rule - same principle applies to arbitrary Python). `config.CALC_TRIGGERS`
  ("quanto e", "quanto da", "calcule", "calcula", "qual o resultado de") alone isn't enough to
  classify as `CALC` - `classify_command()` also requires `extract_expression()` to actually produce
  an expression containing an operator, so a non-math question like "quanto é a distância até a lua"
  correctly falls through to the LLM instead of hitting a confusing "couldn't understand" error.
- **"Bom dia" briefing** (`"bom dia"`, `"resumo do dia"`): `commands._morning_briefing()` just
  combines the existing `weather.get_weather_report()` (best-effort, skipped on failure) and
  `reminders.get_today_agenda()` from round 16 into one spoken reply - no new logic, purely a
  convenience that reuses two already-built pieces. `config.BRIEFING_TRIGGERS`.
- **Offline wake-word detection** (optional, Picovoice Porcupine): previously the *only* way Nico
  checked whether it had been called was sending every ~5-second audio window to Google's cloud
  speech API, even during idle listening. New `wake_word.py` wraps `pvporcupine` (installed and its
  `create()` API signature confirmed live in this session; `pyaudio` was already a dependency via
  `SpeechRecognition`) to do that check 100% locally and instantly, with zero network calls, using a
  custom-trained "Nico" keyword model (a `.ppn` file). `voice.voice_cycle()` now branches on
  `wake_word.is_available()` each cycle: if a `PICOVOICE_ACCESS_KEY` and `PICOVOICE_KEYWORD_PATH` are
  configured in `.env`, it blocks locally on `wake_word.listen_for_wake_word()`; otherwise (the
  default, nothing configured) it falls back to the exact original cloud-based flow
  (`voice._cloud_wake_word_detected()`, a pure extraction of the old logic with no behavior change).
  If Porcupine fails to initialize for any reason (bad key, missing file), it logs the error and falls
  back to one cloud-based check for that cycle rather than crashing the voice loop.
  - **This needs the user's own action to actually turn on** - exactly like Groq/Gemini/Tavily/Google
    Drive before it, since it needs a personal (free) Picovoice account: sign up at
    console.picovoice.ai, copy the Access Key, train a custom wake word named "Nico" (Porcupine has
    native Portuguese-language support for custom wake words, confirmed via Picovoice's own docs
    before telling the user to pick that option in the console), choose Windows as the platform,
    download the generated `.ppn` file, and set `PICOVOICE_ACCESS_KEY`/`PICOVOICE_KEYWORD_PATH` in
    `.env`. Until then, Nico behaves exactly as before - this is additive, not a replacement.
  - **Honesty about testing limits**: the `pvporcupine` import, its `create()` function signature, and
    `is_available()`'s graceful "not configured" behavior were all verified live in this session. The
    actual live microphone wake-word detection loop (`listen_for_wake_word()`'s `while True` reading
    real audio frames) could **not** be tested end-to-end in this session, since that requires a real
    Picovoice Access Key and a trained "Nico" `.ppn` file, neither of which exist yet - the user needs
    to do the account setup first and then test it live themselves.
- `requirements.txt` gained `pvporcupine`. `pyttsx3`/`PyAudio` etc. were already present.
- Verified: full `py_compile` across every module including the two new ones; `classify_command()`/
  `handle_command()` tests for the calculator (including the "not actually math" negative case) and
  the briefing (a real end-to-end call that hit live weather + the agenda feature from round 16); a
  live, no-config `wake_word.is_available()` check confirming it returns `False` and the voice loop's
  fallback path is unchanged when nothing is configured.

### Follow-up round 18: YouTube search (2026-10-05)

The user asked whether "abra o youtube" could open a specific video - it couldn't, it only opened the
homepage. Added `system_control.search_youtube(query)`, which opens
`https://www.youtube.com/results?search_query=...` for the requested term - not a direct jump to the
first video (that needs the YouTube Data API and a Google Cloud API key, explicitly not set up without
the user deciding they want that extra account/key), but one click away, and needs nothing new
configured.

- New `YOUTUBE_SEARCH` intent in `classify_command()`: triggers whenever "youtube" is a word in the
  sentence **and** something else is left over after stripping filler words
  (`config.YOUTUBE_SEARCH_FILLER_WORDS` - articles, "abra"/"toca"/"procura"/"pesquisa"/"busca" and
  their variants, "video", "youtube" itself). This check runs *before* the generic `OPEN_PREFIXES`
  check, since "abra um vídeo de X no youtube" starts with "abra " and would otherwise be classified
  as a plain `OPEN` (and fail, since "um vídeo de x no youtube" isn't a known app/site name). A bare
  "abra o youtube" still correctly falls through to `OPEN` as before, since nothing is left over after
  stripping fillers.
- `commands._extract_youtube_query()` does the filler-word stripping; reused by both
  `classify_command()` (to decide if there's a real query) and `handle_command()` (to build the actual
  search URL), so the two don't drift apart.
- Verified: `classify_command()` and `handle_command()` tests confirming "abra o youtube" alone still
  opens the homepage, while "toca lofi no youtube", "abre um vídeo de receita de bolo no youtube", and
  "procura gatos engraçados no youtube" all correctly extract just the search term and open YouTube's
  search results for it.

### Follow-up round 19: real Google Calendar integration (2026-10-06)

The user tested "minha agenda" (round 16) and got "nothing today" despite a full Google Calendar -
revealing that the agenda command only ever looked at Nico's own `reminders` table (things explicitly
said via "lembre que..."), with zero connection to Google Calendar. Real gap, fixed directly:

- **No OAuth app needed**: instead of registering a Google Cloud OAuth app (the heavier, more usual
  path for Calendar access), used Google Calendar's own "secret address in iCal format" - a
  read-only, per-calendar `.ics` feed URL you copy from Calendar's own Settings -> (your calendar) ->
  "Integrate calendar". Much lower setup cost for the user (copy one link, no Cloud Console project,
  no consent screen), at the cost of being read-only (fine, since Nico only needs to *read* the
  agenda, never create/edit events).
- New `google_calendar.py` - `get_today_events()` fetches that feed (`requests`), parses it
  (`icalendar`), and expands recurring events (`recurring_ical_events` - handles `RRULE`/`EXDATE`
  properly for a given date range, which raw `icalendar` alone does not do) to list just today's
  events as `"HH:MM - título"` strings (or `"Dia todo - título"` for all-day events). Best-effort:
  any fetch/parse failure is logged and returns `[]` rather than raising, same pattern as every other
  optional integration in this project. `config.GOOGLE_CALENDAR_ICS_URL` - empty by default, nothing
  changes until the user sets it.
- **Treated as a secret**: that iCal URL lets anyone who has it read the user's whole calendar, so
  it's `.env`-only, never logged or echoed back in chat - same discipline as every API key in this
  project.
- **Emoji in event titles**: the user's real calendar titles turned out to be emoji-prefixed (e.g.
  "🎓 Atividades da faculdade" - from whatever app/habit they use to add events). Spoken aloud by TTS
  this would read oddly, so `google_calendar._clean_summary()` strips common emoji Unicode ranges
  before the title is used in any spoken reply. Caught by testing with the user's actual calendar
  data, not anticipated in advance.
- `commands._combined_agenda_items()` merges Nico's own reminders (`reminders.get_today_agenda()`)
  with `google_calendar.get_today_events()`, sorted together by time, and is now what both the
  `AGENDA` intent and the `"bom dia"` briefing (round 17) use - so both commands show the *real*
  schedule, not just what the user told Nico to remember.
- `requirements.txt` gained `icalendar` and `recurring-ical-events`.
- **Verified with the user's real calendar, live, in this session**: the user pasted their actual
  private iCal URL; it was saved straight to `.env` (never echoed back) and used for a real fetch
  that returned 7 real events for the day (college classes, finance, Spanish, a personal project,
  etc.), correctly ordered, with emoji cleanly stripped from each title, through both "minha agenda"
  and "bom dia" end to end.

### Follow-up round 20: mic pause button in the HUD (2026-10-07)

The user wants to test Nico in public places and needs a quick, visible way to stop it from listening
without closing the app - a mute button.

- `state.py` gained `is_mic_enabled()`/`set_mic_enabled()` (a thread-safe bool, same lock-protected
  pattern as `get_status()`/`set_status()`), defaulting to `True` (listening, as before).
- `voice.voice_cycle()` checks `state.is_mic_enabled()` as its very first step, before either wake-word
  path (offline Porcupine or cloud Google) runs: if paused, it sets the status to `"Pausado"`, sleeps
  briefly, and returns without ever touching `sr.Microphone` - confirmed with a test that replaces
  `sr.Microphone` with a function that raises if called, proving the mic genuinely never opens while
  paused, not just that recognition is skipped after capturing audio.
- `web_server.py`: `/status` now also returns `mic_enabled`; new `POST /mic/toggle` flips it and
  returns the new value.
- `web/index.html` gained a visible mic button (🎤/🔇 + "MICROFONE LIGADO"/"MICROFONE PAUSADO") right
  under the status text; `web/hud.js`'s `refreshStatus()` polls `mic_enabled` from `/status` on its
  existing 500ms interval and keeps the button in sync (so it reflects reality even if toggled from
  another device on the same panel), and `toggleMic()` posts to `/mic/toggle`. `"Pausado"` was added to
  `STATUS_COLORS` (uses `--c-error`, the same red as the error state) so the HUD's glowing core/rings
  visibly go red while paused, not just the button.
- Verified: full `py_compile`; `state.py`'s enable/disable logic tested directly; the real Flask app
  spun up on a throwaway port and hit live over HTTP (`GET /status`, `POST /mic/toggle` twice) to
  confirm the toggle actually flips and persists through `/status`; and the microphone-never-opens
  behavior confirmed as described above. The button's actual on-screen appearance/click behavior in
  the real pywebview window was not visually screenshotted in this session - worth a quick look next
  time the user has the HUD open.

### Follow-up round 21: typed chat commands now speak their answer out loud too (2026-10-07)

Right after round 20 shipped, the user clarified what "respond while the mic is paused" actually
meant: typed commands through `/command` (the HUD's text box) already *worked* (returned the right
answer as text, confirmed in round 20's own testing) - but they never spoke it out loud, since
`/command` just returned JSON for the page to display. With the mic paused being the user's main way
to interact (testing in public), silent text-only replies felt like "not responding."

- `web_server.py`'s `/command` route now also calls `tts.speak()` on the answer, in a background
  `threading.Thread` (daemon) so the HTTP response to the browser isn't held up waiting for the audio
  to finish playing - the JSON comes back immediately, as before, and the voice plays shortly after.
- Deliberately **not** gated on `state.is_mic_enabled()` - the mic-pause button only controls whether
  Nico *listens* (microphone input), not whether it *speaks*; pausing the mic protects ambient-audio
  privacy, it was never about silencing Nico's own voice.
- Verified: the real Flask server spun up on a throwaway port with the mic explicitly paused, hit
  `/command` with a real typed question ("ola") over HTTP, got the correct JSON answer back, and the
  background `speak()` call ran to completion with no exception (the same `tts.speak()` path already
  proven to work with real audio playback in round 14) - actually *hearing* the audio needed the
  user's own ears, flagged honestly rather than claimed as directly verified.

### Follow-up round 22: respostas não apareciam no chat para a maioria dos comandos (2026-10-07)

O usuário testou pelo chat digitado e a resposta não aparecia no transcript do HUD (e não podia
confirmar pelo áudio porque o notebook estava no mudo). Causa real: `state.conversation_history` (a
lista que `/history` expõe e `hud.js` usa para desenhar o transcript) só recebia um `.append(...)`
dentro de `commands._get_llm_answer`'s caller - ou seja, só quando a pergunta caía no caminho do LLM
(cache miss no banco de Q&A). Qualquer comando que respondia por um atalho direto (`"oi"`, `"que
horas são"`, `"bom dia"`, calculadora, agenda, abrir app/site, volume, etc. - a grande maioria dos
comandos do projeto) nunca era adicionado ao histórico, então o HUD simplesmente não mostrava nada,
mesmo a resposta estando correta (e sendo falada, quando o microfone/áudio funcionava).

- `commands.handle_command()`/`resolve_clarification()` deixaram de fazer
  `conversation_history.append(...)` internamente - isso ficava restrito ao caminho do LLM, então
  comandos simples nunca passavam por ali.
- Centralizado em vez disso nos dois pontos que realmente chamam `handle_command()`:
  `web_server.py`'s `/command` (adiciona `(text, result.text)` ao `state.conversation_history` logo
  após obter o resultado, para qualquer tipo de comando) e `voice.voice_cycle()` (adiciona nos três
  ramos - `CLARIFY` resolvido, `INCOMPLETE`, e resposta normal). `save_conversation()` (grava no
  banco `conversation` pra cache futura) continua só acontecendo no caminho do LLM, como antes - isso
  é intencional, não queremos poluir o cache de Q&A com "que horas são" -> "14:32", que fica
  desatualizado no mesmo instante.
- Verificado diretamente (sem depender de áudio, já que o notebook estava mudo): chamada real de
  `handle_command()` para "oi", "que horas sao" e "bom dia" (essa última bateu de verdade no clima e
  na agenda/Google Calendar reais), confirmando que agora as três entram em
  `state.conversation_history` - antes nenhuma delas entrava.

### Follow-up round 23: pesquisa com objetivo e exclusões obrigatórios

- O modo Pesquisa aceita o formato `Modo Pesquisa <tema>, <o que quero>, <o que não quero>`.
  Os três campos são obrigatórios; se faltar algum, `commands.py` pergunta pelo campo e mantém o
  pedido pendente em `state.py`, funcionando tanto pela voz quanto pelo HUD. O usuário pode cancelar
  com "cancelar pesquisa".
- `research.py` inclui o objetivo na consulta Tavily e passa objetivo e exclusões ao prompt de
  síntese. Se as fontes não sustentarem os critérios, o relatório deve declarar essa limitação,
  sem preencher com conteúdo fora do escopo. `run_research()` também valida os campos antes de
  iniciar a busca.

## Future Goals (explicitly deferred, not started)

- Phone notifications and/or calls - previously implemented via CallMeBot (Telegram), removed in round
  13 because CallMeBot started requiring payment. A real phone call through the carrier still needs an
  external telephony service (e.g. Twilio, usually paid) or a companion phone app; a local Python
  script alone cannot place a real carrier phone call. If the user wants this back, a genuinely free
  alternative would need to be found first.
- Reading the user's existing "Cursos" (or other) Drive folders is supported (`.docx` reader is ready)
  but not wired up - add the path to `NOTES_FOLDER`/`DOCUMENT_FOLDERS` if/when the user wants it
  searched.
- Deeper phone/tablet OS integration beyond the local web panel (notifications, contacts, a real
  mobile app) - the web panel in `web_server.py` is the current, lighter-weight version.
- `DOCUMENTS_FOLDER` still needs to be filled in once the user installs Google Drive Desktop and
  confirms the local synced path for the "Nico Research" folder.
- Camera-based features (facial recognition for security/unlock, or controlling the PC via hand/body
  movement) - explicitly raised by the user as "just an idea for later," not something to build now.
  Would need a dedicated vision library (e.g. OpenCV + a face-recognition model, or a gesture model)
  and a clear decision on what "security" should actually do (lock the screen? something else?) -
  bigger scope than anything implemented so far, and camera access/face data is sensitive enough that
  this needs its own explicit go-ahead and design discussion when the user is ready to pick it up.
- Gmail/Notion/other OAuth-based connectors (raised when reviewing some AI-assistant blueprint posts
  the user shared on 2026-10-05) - genuinely new capability, but needs OAuth app registration/
  credentials the user has to set up and explicitly approve first; not started.

## Working Mode

The incremental teaching workflow below no longer applies to this project - the user asked Claude to
finish it directly. Keep this section for historical context only:

- ~~Teach one small command or concept at a time.~~
- ~~Do not edit project code automatically unless the user explicitly asks for edits.~~
- ~~Let the user type the code and then review it.~~
- ~~For every change, explain: whether the usage is correct, a possible improvement and its effect,
  and whether it is safe.~~
- ~~Explain the cause of errors before presenting a correction.~~

From now on: implement what's asked directly, explain what changed and why after the fact, and still
flag anything risky or destructive before doing it (see Safety and Data below).

## Safety and Data

- Keep `nico_memory.db` and `.env` out of Git; they are listed in `.gitignore`. `.env.example` (no
  real keys, just instructions) is safe to commit.
- Use SQLite parameter placeholders (`?`) for user or model text.
- Do not let the voice input or Ollama generate and execute arbitrary SQL.
- Require explicit confirmation before destructive actions or dynamic schema changes.
- Never hardcode a real Groq/Gemini/Tavily API key in source - they must only ever come from `.env`
  (via `python-dotenv`) or the environment.

## Validation

From the project directory:

```powershell
py -3.11 -m py_compile config.py text_utils.py database.py memory.py llm.py cloud_llm.py web_search.py documents.py facts.py reminders.py system_control.py weather.py research.py calculator.py wake_word.py google_calendar.py commands.py tts.py voice.py state.py web_server.py desktop_app.py nico.py
py -3.11 nico.py
```

The local Ollama endpoint is `http://localhost:11434/api/generate`.
The local web panel listens on `http://0.0.0.0:5000` (printed with the LAN URL on startup, both the
`localhost` and LAN addresses). Windows Firewall may prompt to allow Python on first run - accept it
for the private network, or the phone panel won't be reachable from other devices.
Optional cloud keys go in a local `.env` file - copy `.env.example` to `.env` and fill in whichever
keys you want (`GROQ_API_KEY`, `GEMINI_API_KEY`, `TAVILY_API_KEY`); all are optional.
