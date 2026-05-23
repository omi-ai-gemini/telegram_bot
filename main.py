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
# BOT-SET UI (✔ 完整替換版)
# =========================
def handle_bot_set(user_id, text, chat_id):

    state = USER_STATE.get(user_id, STATE_NORMAL)

    # -------------------------
    # ADD FLOW
    # -------------------------
    if state == STATE_ADD:
        add_bot(text)
        USER_STATE[user_id] = STATE_NORMAL
        send(chat_id, f"bot: add-bot\n[{text}] 已加入群組")
        return True

    # -------------------------
    # DELETE FLOW
    # -------------------------
    if state == STATE_DELETE:
        delete_bot(text)
        USER_STATE[user_id] = STATE_NORMAL
        send(chat_id, f"bot: {text} 已退出群組")
        return True

    # -------------------------
    # COMMANDS
    # -------------------------
    if text.startswith("[ add ]"):
        USER_STATE[user_id] = STATE_ADD
        send(chat_id, "bot: add-bot\n請輸入 bot 名稱")
        return True

    if text.startswith("[ delete ]"):
        USER_STATE[user_id] = STATE_DELETE
        send(chat_id, "bot: delete-bot\n請輸入要刪除的 bot 名稱")
        return True

    # -------------------------
    # VIEW BOT SETTING（✔ 你要的）
    # -------------------------
    if text.startswith("[") and text.endswith("]"):

        bot_id = text.replace("[", "").replace("]", "").strip()

        bots = get_bots()

        for b in bots:
            if b[0] == bot_id:

                send(chat_id, f"""bot:
[{b[0]}]
性格: {b[2]}
""")
                return True

        send(chat_id, "bot: 尚未找到該 bot")
        return True

    return False


# =========================
# GEMINI（✔ 已加名字前綴）
# =========================
def ask_gemini(text, world):

    bots = get_bots()

    if len(bots) == 0:
        return "bot: 尚無bot加入群組，請先使用 [ add ] 新增角色"

    npc_info = "\n".join([f"{b[0]}:{b[2]}" for b in bots])

    prompt = f"""
你是群組AI

世界:
{world}

NPC:
{npc_info}

使用者:
{text}

請用「角色名稱:內容」格式回覆
例如：
小明: 我覺得可以
"""

    return model.generate_content(prompt).text


# =========================
# NPC SYSTEM（✔ 已加名字）
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
請直接輸出一句話，不要解釋
"""

    msg = model.generate_content(prompt).text

    # ✔ 加名字（你要求的）
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

    # ✔ bot-set 優先
    if handle_bot_set(user_id, text, chat_id):
        return "ok"

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