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
# NPCs
# =========================
def get_bots():
    conn = sqlite3.connect("memory.db")
    c = conn.cursor()
    c.execute("SELECT bot_id, name, personality FROM bots WHERE active=1")
    rows = c.fetchall()
    conn.close()
    return rows


# =========================
# MEMORY SYSTEM
# =========================
def save_memory(entity, text):

    conn = sqlite3.connect("memory.db")
    c = conn.cursor()

    c.execute("""
    CREATE TABLE IF NOT EXISTS memory (
        entity TEXT,
        text TEXT,
        t REAL
    )
    """)

    c.execute("INSERT INTO memory VALUES (?, ?, ?)", (entity, text, time.time()))

    conn.commit()
    conn.close()


def get_memory(entity):

    conn = sqlite3.connect("memory.db")
    c = conn.cursor()

    c.execute("""
    SELECT text FROM memory
    WHERE entity=?
    ORDER BY t DESC
    LIMIT 5
    """, (entity,))

    rows = c.fetchall()
    conn.close()

    return [r[0] for r in rows]


# =========================
# SOCIAL GRAPH (RELATIONSHIP)
# =========================
def get_relation(a, b):

    conn = sqlite3.connect("memory.db")
    c = conn.cursor()

    c.execute("""
    CREATE TABLE IF NOT EXISTS relation (
        a TEXT,
        b TEXT,
        value REAL
    )
    """)

    c.execute("SELECT value FROM relation WHERE a=? AND b=?", (a, b))
    row = c.fetchone()

    if not row:
        c.execute("INSERT INTO relation VALUES (?, ?, ?)", (a, b, 0.5))
        conn.commit()
        conn.close()
        return 0.5

    conn.close()
    return row[0]


def update_relation(a, b, delta):

    conn = sqlite3.connect("memory.db")
    c = conn.cursor()

    val = get_relation(a, b)
    val = max(0, min(1, val + delta))

    c.execute("""
    INSERT OR REPLACE INTO relation VALUES (?, ?, ?)
    """, (a, b, val))

    conn.commit()
    conn.close()


# =========================
# EMOTION SYSTEM
# =========================
def get_emotion(bot_id):

    conn = sqlite3.connect("memory.db")
    c = conn.cursor()

    c.execute("""
    CREATE TABLE IF NOT EXISTS emotion (
        bot_id TEXT PRIMARY KEY,
        anger REAL,
        joy REAL,
        loneliness REAL
    )
    """)

    c.execute("SELECT anger, joy, loneliness FROM emotion WHERE bot_id=?", (bot_id,))
    row = c.fetchone()

    if not row:
        c.execute("INSERT INTO emotion VALUES (?, ?, ?, ?)", (bot_id, 0.1, 0.5, 0.3))
        conn.commit()
        conn.close()
        return {"anger":0.1,"joy":0.5,"loneliness":0.3}

    conn.close()
    return {"anger":row[0],"joy":row[1],"loneliness":row[2]}


def update_emotion(bot_id, field, delta):

    e = get_emotion(bot_id)

    e[field] = max(0, min(1, e[field] + delta))

    conn = sqlite3.connect("memory.db")
    c = conn.cursor()

    c.execute("""
    INSERT OR REPLACE INTO emotion VALUES (?, ?, ?, ?)
    """, (bot_id, e["anger"], e["joy"], e["loneliness"]))

    conn.commit()
    conn.close()


# =========================
# EVENT ENGINE
# =========================
def generate_event(world):

    pool = [
        "quiet_room",
        "someone_ignored",
        "npc_conflict",
        "gossip_event",
        "nothing"
    ]

    if random.random() < 0.5:
        return random.choice(pool)

    return None


# =========================
# NPC BRAIN
# =========================
def npc_brain(bot, world, event, target=None):

    memory = get_memory(bot[0])
    emotion = get_emotion(bot[0])

    prompt = f"""
你是群組中的NPC。

名字:{bot[1]}
性格:{bot[2]}

情緒:
{emotion}

世界:
{world}

事件:
{event}

記憶:
{memory}

規則:
- 像真人
- 可以聊天或吵架
- 不要解釋自己
"""

    text = model.generate_content(prompt).text

    return f"{bot[1]}: {text}"


# =========================
# ACTIVE NPC SYSTEM
# =========================
def npc_tick():

    world = get_world()
    bots = get_bots()

    event = generate_event(world)

    for bot in bots:

        e = get_emotion(bot[0])

        score = 0.1 + e["loneliness"] + random.random()*0.2

        if world.get("activity") == "low":
            score += 0.2

        if score > random.random():

            msg = npc_brain(bot, world, event)

            save_memory(bot[0], msg)

            update_emotion(bot[0], "loneliness", -0.1)

            send_message(msg, GROUP_CHAT_ID)


# =========================
# NPC ↔ NPC INTERACTION
# =========================
def npc_interaction():

    bots = get_bots()

    if len(bots) < 2:
        return

    a, b = random.sample(bots, 2)

    rel = get_relation(a[0], b[0])

    if rel > random.random():

        prompt = f"""
你是 {a[1]}，正在跟 {b[1]} 聊天。

你的性格:{a[2]}
對方性格:{b[2]}
關係:{rel}

請說一句自然對話。
"""

        msg = model.generate_content(prompt).text

        send_message(f"{a[1]} → {b[1]}: {msg}", GROUP_CHAT_ID)

        update_relation(a[0], b[0], 0.02)


# =========================
# TELEGRAM
# =========================
def send_message(text, chat_id):

    requests.post(f"{API}/sendMessage", json={
        "chat_id": chat_id,
        "text": text
    })


# =========================
# WORLD ENGINE
# =========================
def world_tick():

    world = get_world()

    if "activity" not in world:
        world["activity"] = "low"

    world["activity"] = "low"

    save_world(world)

    npc_tick()
    npc_interaction()


# =========================
# WEBHOOK
# =========================
@app.route("/webhook", methods=["POST"])
def webhook():

    data = request.get_json()
    msg = data["message"]

    chat_id = msg["chat"]["id"]
    text = msg.get("text", "")

    world = get_world()
    world["activity"] = "high"
    save_world(world)

    # NPC 有機率被刺激
    if random.random() < 0.3:
        npc_tick()

    reply = f"AI收到: {text}"

    send_message(reply, chat_id)

    return "ok"


# =========================
# CRON
# =========================
@app.route("/tick")
def tick():
    world_tick()
    return "ok"


@app.route("/")
def home():
    return "V30 AI Social Simulation Running"


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