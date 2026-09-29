import pyttsx3
import datetime
import sqlite3
import string
import gc
import threading
import speech_recognition as sr
import customtkinter as ctk
import requests

def speak(text):
    set_status("Speaking")
    voice_engine = pyttsx3.init()
    voices = voice_engine.getProperty("voices")
    voice_engine.setProperty("voice", voices[1].id)
    voice_engine.say(text)
    voice_engine.runAndWait()
    voice_engine.stop()
    del voice_engine
    gc.collect()
recognizer = sr.Recognizer()

wake_words = ["nico","nicolò", "nicolo", "nick", "nic"]
wake_word_aliases = {
    "niko": "nico",
    "nikko": "nico",
    "nicco": "nico",
    "nicko": "nico",
    "nicola": "nico",
    "nicol": "nico",
}

def is_wake_word(text):
    normalized = normalize_text(text)
    if not normalized:
        return False

    tokens = normalized.split()
    for token in tokens:
        if token in wake_words:
            return True
        alias = wake_word_aliases.get(token)
        if alias in wake_words:
            return True

    return False

conversation_history = []

def build_context_prompt(command_text):
    if not conversation_history:
        return command_text

    recent = conversation_history[-5:]
    context = "\n".join(
        f"User: {user}\nAssistant: {assistant}"
        for user, assistant in recent
    )
    return f"{context}\nUser: {command_text}\nAssistant:"

def open_database():
    return sqlite3.connect("nico_memory.db")

def create_table():
    connection = open_database()
    connection.execute("""CREATE TABLE IF NOT EXISTS conversation(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_text TEXT,
    assistant_text TEXT
    )""")
    connection.commit()
    connection.close()

def save_conversation(user_text, assistant_text):
    connection = open_database()
    connection.execute(
        "INSERT INTO conversation (user_text, assistant_text) VALUES (?, ?)",
        (user_text, assistant_text)
    )
    connection.commit()
    connection.close()

def find_conversation(user_text):
    connection = open_database()
    cursor = connection.execute(
        """SELECT assistant_text
        FROM conversation
        WHERE user_text LIKE ?""",
        (user_text,)
    )
    result = cursor.fetchone()
    if result is not None:
        answer = result[0]
    else:
        answer = None
    connection.close()
    return answer

def ask_ollama(prompt):
    response = requests.post(
        "http://localhost:11434/api/generate",
        json={
            "model": "qwen2.5:1.5b",
            "prompt": (
                "You are Nico, a friendly local voice assistant. "
                "Reply in short, natural English. "
                "Keep replies warm, simple, and under two sentences. "
                "Do not refuse normal conversation. "
                "If the user asks for the current time, reply exactly [TIME]. "
                "If the user says hello or asks how you are, answer politely and briefly. "
                "Examples:\n"
                "User: hello\n"
                "Assistant: Hello! How can I help you today?\n"
                "User: how are you doing\n"
                "Assistant: I'm doing well, thanks for asking. How can I help?\n"
                "User: what time is it\n"
                "Assistant: [TIME]\n"
                f"User: {prompt}\n"
                "Assistant:"
            ),
            "stream": False,
            "options": {
                "temperature": 0.3
            }
        },
        timeout=180,
    )
    response.raise_for_status()
    return response.json()["response"]

def get_current_time():
    current_time = datetime.datetime.now()
    return current_time.strftime("%I:%M %p")

def normalize_text(text):
    clean_text = text.lower()
    clean_text = clean_text.translate(
        str.maketrans("", "", string.punctuation)
    )
    return " ".join(clean_text.split())

def classify_command(command_text):
    normalized = normalize_text(command_text)
    words = normalized.split()

    if any(word in {"time", "hour", "clock"} for word in words):
        return "TIME"

    if any(word in {"hello", "hi", "hey"} for word in words):
        return "GREETING"

    if "how are you" in normalized or "how are you doing" in normalized:
        return "MOOD"

    if "thank you" in normalized:
        return "THANKS"

    if "what can you do" in normalized or "what are you able to do" in normalized:
        return "CAPABILITIES"

    if "who are you" in normalized or "what are you" in normalized:
        return "IDENTITY"

    return "LLM"

def handle_command(command_text):
    command_type = classify_command(command_text)

    if command_type == "LLM":
        saved_answer = find_conversation(command_text)
        if saved_answer is not None:
            print("Cache Hit - Resposta do BdD")
            return saved_answer
        print("Cache Miss - Resposta do Ollama")
        answer = ask_ollama(build_context_prompt(command_text))
        conversation_history.append((command_text, answer))
        save_conversation(command_text, answer)
        return answer

    if command_type == "TIME":
        return f"The time is {get_current_time()}."

    if command_type == "GREETING":
        return "Hello! How can I help you today?"

    if command_type == "MOOD":
        return "I'm doing well, thanks for asking. How can I help?"

    if command_type == "THANKS":
        return "You're welcome!"

    if command_type == "CAPABILITIES":
        return "I can answer questions, tell the time, chat with you, and help with simple local tasks."

    if command_type == "IDENTITY":
        return "I'm Nico, your local voice assistant."

    answer = ask_ollama(command_text)
    if answer.strip() == "[TIME]":
        return f"The time is {get_current_time()}."
    return answer

def voice_cycle():
    set_status("Listening")
    with sr.Microphone() as source:
        recognizer.adjust_for_ambient_noise(source, duration=0.5)
        audio = recognizer.listen(source, timeout=10, phrase_time_limit=5)

    try:
        set_status("Thinking")
        text = recognizer.recognize_google(audio, language="en-US")
    except sr.UnknownValueError:   
        print("I didn't understand what you said. Try again.")
        return

    print("Google heard the wake word:", repr(text))

    if is_wake_word(text):
        speak("Yes? I'm listening.")

        while True:
            try:
                with sr.Microphone() as source:
                    set_status("Listening")
                    command_audio = recognizer.listen(source, timeout=10)
            except sr.WaitTimeoutError:
                print("No command for 10 seconds. Waiting for wake word.")
                break

            try:
                set_status("Thinking")
                command_text = recognizer.recognize_google(
                    command_audio,
                    language="en-US"
                )
                print("Google heard the command:", repr(command_text))

                if not command_text or not command_text.strip():
                    continue

                answer = handle_command(command_text)
                print("Final answer:", repr(answer))
                speak(answer)

            except sr.UnknownValueError:
                print("I didn't understand that command.")
            except requests.RequestException as error:
                print("Ollama request failed:", error)
                speak("I can't reach my local language model right now.")
    else:
        speak("I don't know that command yet.")

def voice_loop():
    while True:
        voice_cycle()

app = ctk.CTk()
app.title("Nico")
app.geometry("420x240")

status_label = ctk.CTkLabel(app, text= "Nico is Starting...")
status_label.pack(pady=40)
def set_status(message):
    app.after(0, lambda: status_label.configure(text=message))

create_table()

voice_thread = threading.Thread(target=voice_loop, daemon=True)
voice_thread.start()

app.mainloop()