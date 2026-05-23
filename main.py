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
# GLOBAL TIMER
# =========================
LAST_NPC_TIME = 0
NPC_COOLDOWN = 6 * 60 * 60  # 6小時


# =========================
# DB
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


def get_bots():
    conn = sqlite3.connect("memory.db")
    c = conn.cursor()
    c.execute("SELECT bot_id, name, personality FROM bots WHERE active=1")
    rows = c.fetchall()
    conn.close()
    return rows


# =========================
# TELEGRAM
# =========================
def send_message(text, chat_id):
    requests.post(f"{API}/sendMessage", json={
        "chat_id": chat_id,
        "text": text
    })


# =========================
# GEMINI CHAT
# =========================
def ask_gemini(text, world):

    bots = get_bots()

    npc_text = "\n".join([f"{b[0]}:{b[2]}" for b in bots])

    prompt = f"""
你是群組AI。

世界:
{world}

NPC:
{npc_text}

使用者:
{text}

請像群組聊天回應。
"""

    return model.generate_content(prompt).text


# =========================
# NPC BRAIN
# =========================
def npc_brain(bot, world):

    prompt = f"""
你是NPC。

名字:{bot[1]}
性格:{bot[2]}

世界:
{world}

請講一句自然群組聊天內容。
"""

    return model.generate_content(prompt).text


# =========================
# NPC TRIGGER（核心）
# =========================
def should_trigger_npc():

    global LAST_NPC_TIME

    now = time.time()

    # ⛔ 未滿6小時不觸發
    if now - LAST_NPC_TIME < NPC_COOLDOWN:
        return False

    # 🎲 50%機率
    if random.random() < 0.5:
        LAST_NPC_TIME = now
        return True

    return False


# =========================
# NPC ACTION
# =========================
def npc_tick():

    if not should_trigger_npc():
        return

    world = get_world()
    bots = get_bots()

    if not bots:
        return

    bot = random.choice(bots)

    msg = npc_brain(bot, world)

    send_message(f"{bot[1]}: {msg}", GROUP_CHAT_ID)


# =========================
# WORLD UPDATE
# =========================
def update_world():
    world = get_world()
    world["activity"] = "low"
    save_world(world)


# =========================
# WEBHOOK
# =========================
@app.route("/webhook", methods=["POST"])
def webhook():

    data = request.get_json()
    msg = data["message"]

    chat_id = msg["chat"]["id"]
    text = msg.get("text", "")

    # 世界變活躍
    world = get_world()
    world["activity"] = "high"
    save_world(world)

    # AI回覆
    reply = ask_gemini(text, world)

    send_message(reply, chat_id)

    return "ok"


# =========================
# TICK (UptimeRobot)
# =========================
@app.route("/tick")
def tick():

    update_world()

    npc_tick()

    return "ok"


# =========================
# HOME
# =========================
@app.route("/")
def home():
    return "V30.1 NPC System Running"