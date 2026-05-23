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
# STATE MACHINE
# =========================
USER_STATE = {}

STATE_NORMAL = "normal"
STATE_ADD = "add_bot"
STATE_DELETE = "delete_bot"


# =========================
# NPC TIMER
# =========================
LAST_NPC_TIME = 0
NPC_COOLDOWN = 6 * 60 * 60


# =========================
# DB INIT
# =========================
def init():
    conn = sqlite3.connect("memory.db")
    c = conn.cursor()

    c.execute("""
    CREATE TABLE IF NOT EXISTS bots (
        bot_id TEXT PRIMARY KEY,
        name TEXT,
        personality TEXT,
        active INTEGER
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


init()


# =========================
# WORLD
# =========================
def get_world():
    conn = sqlite3.connect("memory.db")
    c = conn.cursor()
    c.execute("SELECT key, value FROM world")
    world = {k: v for k, v in c.fetchall()}
    conn.close()
    return world


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
def get_bots():
    conn = sqlite3.connect("memory.db")
    c = conn.cursor()
    c.execute("SELECT bot_id, name, personality FROM bots WHERE active=1")
    rows = c.fetchall()
    conn.close()
    return rows


def add_bot(bot_id, personality="default"):
    conn = sqlite3.connect("memory.db")
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO bots VALUES (?, ?, ?, 1)", 
              (bot_id, bot_id, personality))
    conn.commit()
    conn.close()


def delete_bot(bot_id):
    conn = sqlite3.connect("memory.db")
    c = conn.cursor()
    c.execute("UPDATE bots SET active=0 WHERE bot_id=?", (bot_id,))
    conn.commit()
    conn.close()


# =========================
# TELEGRAM
# =========================
def send(chat_id, text):
    requests.post(f"{API}/sendMessage", json={
        "chat_id": chat_id,
        "text": text
    })


# =========================
# BOT STATE HANDLER
# =========================
def handle_bot_set(user_id, text, chat_id):

    state = USER_STATE.get(user_id, STATE_NORMAL)

    # ========== ADD BOT ==========
    if state == STATE_ADD:
        add_bot(text)
        USER_STATE[user_id] = STATE_NORMAL
        send(chat_id, f"✅ bot 已加入群組：{text}")
        return True

    # ========== DELETE BOT ==========
    if state == STATE_DELETE:
        delete_bot(text)
        USER_STATE[user_id] = STATE_NORMAL
        send(chat_id, f"🗑 bot 已移除：{text}")
        return True

    # ========== COMMAND ==========
    if text.startswith("[ add ]"):
        USER_STATE[user_id] = STATE_ADD
        send(chat_id, "請輸入 bot 名稱")
        return True

    if text.startswith("[ delete ]"):
        USER_STATE[user_id] = STATE_DELETE
        send(chat_id, "請輸入要刪除的 bot 名稱")
        return True

    if text.startswith("["):
        bot_id = text.replace("[", "").replace("]", "").strip()

        bots = get_bots()
        for b in bots:
            if b[0] == bot_id:
                send(chat_id, f"""
bot: {b[0]}
性格: {b[2]}
""")
                return True

    return False


# =========================
# GEMINI
# =========================
def ask_gemini(text, world):

    bots = get_bots()

    if len(bots) == 0:
        return "尚無bot加入群組，請先使用 [ add ] 新增角色"

    npc_info = "\n".join([f"{b[0]}:{b[2]}" for b in bots])

    prompt = f"""
群組AI

世界:
{world}

NPC:
{npc_info}

使用者:
{text}

請自然回覆群組聊天內容
"""

    return model.generate_content(prompt).text


# =========================
# NPC SYSTEM
# =========================
def should_trigger_npc():

    global LAST_NPC_TIME

    now = time.time()

    if now - LAST_NPC_TIME < NPC_COOLDOWN:
        return False

    if random.random() < 0.5:
        LAST_NPC_TIME = now
        return True

    return False


def npc_tick():

    if not should_trigger_npc():
        return

    bots = get_bots()

    if not bots:
        return

    bot = random.choice(bots)

    prompt = f"""
你是NPC {bot[1]}
性格:{bot[2]}

請說一句群組聊天內容
"""

    msg = model.generate_content(prompt).text

    send(GROUP_CHAT_ID, f"{bot[1]}: {msg}")


# =========================
# WEBHOOK
# =========================
@app.route("/webhook", methods=["POST"])
def webhook():

    data = request.get_json()
    msg = data["message"]

    chat_id = msg["chat"]["id"]
    user_id = str(msg["from"]["id"])
    text = msg.get("text", "")

    # BOT SET 優先處理（不進 Gemini）
    if handle_bot_set(user_id, text, chat_id):
        return "ok"

    # 世界
    world = get_world()
    world["activity"] = "high"
    save_world(world)

    reply = ask_gemini(text, world)

    send(chat_id, reply)

    return "ok"


# =========================
# TICK (HEAD SUPPORT)
# =========================
@app.route("/tick", methods=["GET", "HEAD"])
def tick():

    if request.method == "HEAD":
        return "", 200

    npc_tick()

    return "ok"


# =========================
# HOME
# =========================
@app.route("/")
def home():
    return "V31 AI Social Game Running"