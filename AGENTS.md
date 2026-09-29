# Nico Project Guide

## Purpose

Nico is a personal learning project: a local English voice assistant for Windows.
The long-term goal is a reliable daily assistant, not only a prototype.

## Current Stack

- Python 3.11
- SpeechRecognition with Google recognition (`en-US`)
- pyttsx3 for Windows text-to-speech
- CustomTkinter for the GUI
- Ollama with the local model `qwen2.5:1.5b`
- SQLite database in `nico_memory.db`

## Current Architecture

- `voice_loop()` repeatedly runs `voice_cycle()` in a daemon thread.
- The GUI runs in the main thread.
- `set_status()` updates the GUI through `app.after(...)`.
- `handle_command()` routes local commands or LLM conversation.
- `create_table()` creates the `conversation` table.
- `save_conversation()` stores LLM questions and answers.
- `find_conversation()` looks up saved answers.

## Current Phase

Phase 5: persistent memory.

The current memory lookup is exact or pattern-based and is still being refined.
The next planned improvements are normalized keyword search, incomplete-command handling,
and clarification when several memories match.

## Learning Rules

- Teach one small command or concept at a time.
- Do not edit project code automatically unless the user explicitly asks for edits.
- Let the user type the code and then review it.
- For every change, explain: whether the usage is correct, a possible improvement and its effect,
  and whether it is safe.
- Explain the cause of errors before presenting a correction.

## Safety and Data

- Keep `nico_memory.db` and `.env` out of Git; they are listed in `.gitignore`.
- Use SQLite parameter placeholders (`?`) for user or model text.
- Do not let the voice input or Ollama generate and execute arbitrary SQL.
- Require explicit confirmation before destructive actions or dynamic schema changes.

## Validation

From the project directory:

```powershell
py -3.11 -m py_compile nico.py
py -3.11 nico.py
```

The local Ollama endpoint is `http://localhost:11434/api/generate`.
