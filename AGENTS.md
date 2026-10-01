# Nico Project Guide

## Purpose

Nico is a local English voice assistant for Windows, originally started as a personal learning
project. The user decided that learning Python through this project was not working for them and
asked for the project to be finished directly, so they can study Python separately through basic,
dedicated exercises instead. As of this update, the project is considered functionally finished:
all previously planned phases are implemented and the codebase is in a working, reasonably robust
state. Further changes are done directly by Claude on request, without the incremental-teaching
workflow described below.

## Current Stack

- Python 3.11
- SpeechRecognition with Google recognition (`en-US`)
- edge-tts (Microsoft Edge neural voice, `en-US-GuyNeural`) as the primary voice, pygame for
  playback; pyttsx3 kept only as an offline fallback voice
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
- `notify.py` - `send_telegram_message()`: free Telegram notifications via CallMeBot, no API key (see
  "Follow-up round 6" below).
- `reminders.py` - `parse_due_date()`, `maybe_schedule_reminder()`, `check_due_reminders()`,
  `reminder_loop()`: natural-language date/time parsing (`dateparser`) plus a background thread that
  fires due reminders via Telegram and local speech (see "Follow-up round 7" below).
- `system_control.py` - `open_target()`, `volume_up()`/`volume_down()`/`volume_mute()`,
  `take_screenshot()`, `get_battery_status()` (see "Follow-up round 9" below).
- `weather.py` - `get_weather_report()`: free weather via Open-Meteo, no API key (see "Follow-up
  round 9" below).
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
  `nico.py`.
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
- `documents.py` now also reads `.docx` files (via `python-docx`), not just `.txt`/`.md` - paragraphs
  between blank lines become sections, same as the text-file case. No folder is pointed at `.docx`
  content yet (e.g. the user's "Cursos" folder) - that's opt-in, add it to `.env` as a third
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

## Future Goals (explicitly deferred, not started)

- Phone calling from Nico - needs an external telephony service (e.g. Twilio, usually paid) or a
  companion phone app; a local Python script alone cannot place phone calls.
- Reading the user's existing "Cursos" (or other) Drive folders is supported (`.docx` reader is ready)
  but not wired up - add the path to `NOTES_FOLDER`/`DOCUMENT_FOLDERS` if/when the user wants it
  searched.
- Deeper phone/tablet OS integration beyond the local web panel (notifications, contacts, a real
  mobile app) - the web panel in `web_server.py` is the current, lighter-weight version.
- `DOCUMENTS_FOLDER` still needs to be filled in once the user installs Google Drive Desktop and
  confirms the local synced path for the "Nico Research" folder.

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
py -3.11 -m py_compile config.py text_utils.py database.py memory.py llm.py cloud_llm.py web_search.py commands.py tts.py voice.py state.py web_server.py desktop_app.py nico.py
py -3.11 nico.py
```

The local Ollama endpoint is `http://localhost:11434/api/generate`.
The local web panel listens on `http://0.0.0.0:5000` (printed with the LAN URL on startup, both the
`localhost` and LAN addresses). Windows Firewall may prompt to allow Python on first run - accept it
for the private network, or the phone panel won't be reachable from other devices.
Optional cloud keys go in a local `.env` file - copy `.env.example` to `.env` and fill in whichever
keys you want (`GROQ_API_KEY`, `GEMINI_API_KEY`, `TAVILY_API_KEY`); all are optional.
