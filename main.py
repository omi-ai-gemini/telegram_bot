from flask import Flask, request
import os
import requests
import sqlite3
import time
import random
import google.generativeai as genai

app = Flask(__name__)

# =========================
# CONFIG
# =========================
BOT_TOKEN = os.getenv("BOT_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GROUP_CHAT_ID = os.getenv("GROUP_CHAT_ID")

API = f"https://api.telegram.org/bot{BOT_TOKEN}"

genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("gemini-2.5-flash")


# =========================
# DB INIT
# =========================
def init_db():

    conn = sqlite3.connect("memory.db")
    c = conn.cursor()

    c.execute("""
    CREATE TABLE IF NOT EXISTS bots (
        bot_id TEXT PRIMARY KEY,
        gender TEXT,
        personality TEXT,
        base_affinity REAL,
        active INTEGER
    )
    """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS session (
        user_id TEXT PRIMARY KEY,
        state TEXT,
        buffer TEXT
    )
    """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS world (
        key TEXT PRIMARY KEY,
        value TEXT
    )
    """)

    conn.commit()
    conn.close()


# =========================
# WORLD
# =========================
def get_world():
    conn = sqlite3.connect("memory.db")
    c = conn.cursor()
    c.execute("SELECT key, value FROM world")
    rows = c.fetchall()
    conn.close()
    return {k: v for k, v in rows}


def save_world(world):
    conn = sqlite3.connect("memory.db")
    c = conn.cursor()

    for k, v in world.items():
        c.execute("INSERT OR REPLACE INTO world VALUES (?, ?)", (k, str(v)))

    conn.commit()
    conn.close()


# =========================
# BOT CRUD
# =========================
def create_bot(bot_id, data):

    conn = sqlite3.connect("memory.db")
    c = conn.cursor()

    c.execute("""
    INSERT INTO bots VALUES (?, ?, ?, ?, 1)
    """, (
        bot_id,
        data.get("性別", ""),
        data.get("性格", ""),
        float(data.get("基礎好感度", 0.5))
    ))

    conn.commit()
    conn.close()


def delete_bot(bot_id):

    conn = sqlite3.connect("memory.db")
    c = conn.cursor()

    c.execute("DELETE FROM bots WHERE bot_id=?", (bot_id,))

    conn.commit()
    conn.close()


def show_bot(bot_id):

    conn = sqlite3.connect("memory.db")
    c = conn.cursor()

    c.execute("SELECT * FROM bots WHERE bot_id=?", (bot_id,))
    row = c.fetchone()

    conn.close()

    if not row:
        return "⚠️ 找不到 NPC"

    return f"""
[ {row[0]} ]
性別: {row[1]}
性格: {row[2]}
基礎好感度: {row[3]}
"""


# =========================
# SESSION
# =========================
def get_session(user_id):

    conn = sqlite3.connect("memory.db")
    c = conn.cursor()

    c.execute("SELECT state, buffer FROM session WHERE user_id=?", (user_id,))
    row = c.fetchone()

    conn.close()

    if not row:
        return {"state": "IDLE", "buffer": ""}

    return {"state": row[0], "buffer": row[1]}


def save_session(user_id, state, buffer):

    conn = sqlite3.connect("memory.db")
    c = conn.cursor()

    c.execute("""
    INSERT OR REPLACE INTO session VALUES (?, ?, ?)
    """, (user_id, state, buffer))

    conn.commit()
    conn.close()


# =========================
# PARSER (SAFE)
# =========================
VALID_FIELDS = {"性別", "性格", "基礎好感度"}

def parse_fields(text):

    data = {}

    for line in text.split("\n"):
        if ":" not in line:
            continue

        k, v = line.split(":", 1)

        if k.strip() in VALID_FIELDS:
            data[k.strip()] = v.strip()

    return data


# =========================
# STATE MACHINE
# =========================
def is_setting(text):
    return text.strip().endswith("setting")


def handle_setting_flow(user_id, text):

    session = get_session(user_id)
    state = session["state"]

    # =====================
    # IDLE
    # =====================
    if state == "IDLE":

        if text.startswith("[ add ]"):
            bot_id = text.split("]:")[-1].strip()
            save_session(user_id, "ADD", bot_id)

            return f"bot: add-bot\n[ {bot_id} ]\n性別:\n性格:\n基礎好感度:0.5"

        if text.startswith("[ delete ]"):
            bot_id = text.split("]:")[-1].strip()
            save_session(user_id, "DELETE", bot_id)

            return f"是否刪除 {bot_id} ?（是 / 否）"

        if text.startswith("["):
            bot_id = text.replace("[", "").replace("]", "").strip()
            save_session(user_id, "EDIT", bot_id)

            return show_bot(bot_id)

        return None


    # =====================
    # ADD MODE
    # =====================
    if state == "ADD":

        if is_setting(text):

            bot_id = session["buffer"]
            data = parse_fields(text)

            create_bot(bot_id, data)

            save_session(user_id, "IDLE", "")

            return f"✅ {bot_id} 已加入群組"

        return None


    # =====================
    # EDIT MODE
    # =====================
    if state == "EDIT":

        if is_setting(text):

            bot_id = session["buffer"]
            data = parse_fields(text)

            conn = sqlite3.connect("memory.db")
            c = conn.cursor()

            for k, v in data.items():
                c.execute(f"UPDATE bots SET {k}=? WHERE bot_id=?", (v, bot_id))

            conn.commit()
            conn.close()

            save_session(user_id, "IDLE", "")

            return f"✅ 更新完成\n\n{show_bot(bot_id)}"

        return None


    # =====================
    # DELETE CONFIRM
    # =====================
    if state == "DELETE":

        if "是" in text:

            bot_id = session["buffer"]
            delete_bot(bot_id)

            save_session(user_id, "IDLE", "")

            return f"❌ {bot_id} 已退出群組"

        save_session(user_id, "IDLE", "")
        return "已取消"

    return None


# =========================
# GEMINI (ONLY CHAT)
# =========================
def ask_gemini(user_id, text, world):

    conn = sqlite3.connect("memory.db")
    c = conn.cursor()
    c.execute("SELECT bot_id, personality FROM bots WHERE active=1")
    bots = c.fetchall()
    conn.close()

    bot_context = "\n".join([f"{b[0]}:{b[1]}" for b in bots])

    prompt = f"""
你是群組AI。

世界:
{world}

NPC:
{bot_context}

使用者:
{text}

規則:
- 像群組聊天
- 可以插話
- 不要提系統
"""

    return model.generate_content(prompt).text


# =========================
# TELEGRAM
# =========================
def send_message(text, chat_id):

    requests.post(f"{API}/sendMessage", json={
        "chat_id": chat_id,
        "text": text
    })


# =========================
# WEBHOOK
# =========================
@app.route("/webhook", methods=["POST"])
def webhook():

    data = request.get_json()
    msg = data["message"]

    chat_id = msg["chat"]["id"]
    user_id = str(chat_id)
    text = msg.get("text", "")

    # =====================
    # 1. BOT SETTING (NO GEMINI)
    # =====================
    setting_reply = handle_setting_flow(user_id, text)

    if setting_reply:
        send_message(setting_reply, chat_id)
        return "ok"

    # =====================
    # 2. WORLD UPDATE
    # =====================
    world = get_world()
    world["activity"] = "high"
    save_world(world)

    # =====================
    # 3. GEMINI CHAT ONLY
    # =====================
    reply = ask_gemini(user_id, text, world)

    send_message(reply, chat_id)

    return "ok"


# =========================
# INIT
# =========================
@app.route("/")
def home():
    return "V11.2 Stable AI Social Simulation Running"


init_db()