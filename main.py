#v1
#🧠 記憶（短期）
#❤️ 情緒狀態
#🌐 關係感（trust / familiarity）
#🧩 人格提示層
#🤖 Gemini 推理核心
#v2.5
#🟣 1. 長期記憶（SQLite / Vector DB）
#👉 不只是暫存
#🌍 2. 群組社會模擬
#👉 多人互動關係網
#🤖 3. Tool use AI
#👉 會查資料、操作 API
#🧠 4. 真人格生成器
#👉 自動生成 personality
#v4
#💾 長期記憶
#✔ 每個 user 永久保存對話
#🌐 社會關係系統
#✔ trust / closeness 持久化
#🧠 AI 行為變化
#✔ Gemini 根據人際關係改變語氣
#🧍 群組雛形
#✔ 每個人都是獨立「社會節點」
#v5
#✔ 會判斷：
#✔ 會行為改變：
#✔ 會「社會分層」
#v6
#🧠 Social Simulation v6（AI 社會模擬系統）
#你現在要做的不是讓 AI 更會講話，而是讓它：
#🔥「在多使用者之間形成關係、偏好、記憶分裂與社會行為」
#v7
#🏛️ Social Simulation v7（社會結構 / 陣營系統）
#你現在不是在做 bot，也不是 AI assistant，而是在做：
#🔥「小型數位社會（Digital Society Simulation）」
#v7.5
#🔥 1. 主動觸發系統（Idle Detector）
#🤖 2. 主動 NPC（AI 自發講話）
from flask import Flask, request
import os
import requests
import sqlite3
import time
import random
import google.generativeai as genai

app = Flask(__name__)

# =========================
# 🔑 CONFIG
# =========================
BOT_TOKEN = os.getenv("BOT_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

API = f"https://api.telegram.org/bot{BOT_TOKEN}"

genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("gemini-2.5-flash")

# =========================
# ⏱ GLOBAL STATE
# =========================
LAST_ACTIVE = {
    "group": time.time()
}

IDLE_THRESHOLD = 120  # 2分鐘沒人說話就可能插話


# =========================
# 🧱 DB INIT
# =========================
def init_db():
    conn = sqlite3.connect("memory.db")
    c = conn.cursor()

    c.execute("""
    CREATE TABLE IF NOT EXISTS memory (
        user_id TEXT,
        text TEXT,
        importance REAL
    )
    """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS social (
        user_id TEXT PRIMARY KEY,
        trust REAL,
        closeness REAL,
        importance REAL
    )
    """)

    conn.commit()
    conn.close()


# =========================
# 💾 MEMORY
# =========================
def save_memory(user_id, text):

    importance = 0.2
    keywords = ["重要", "生氣", "難過", "喜歡", "討厭"]

    if any(k in text for k in keywords):
        importance += 0.5

    conn = sqlite3.connect("memory.db")
    c = conn.cursor()

    c.execute("INSERT INTO memory VALUES (?, ?, ?)", (user_id, text, importance))

    conn.commit()
    conn.close()


def get_memory(user_id):
    conn = sqlite3.connect("memory.db")
    c = conn.cursor()

    c.execute("""
    SELECT text FROM memory
    WHERE user_id=?
    ORDER BY importance DESC
    LIMIT 8
    """, (user_id,))

    rows = c.fetchall()
    conn.close()

    return [r[0] for r in rows]


# =========================
# 🌐 SOCIAL
# =========================
def get_social(user_id):
    conn = sqlite3.connect("memory.db")
    c = conn.cursor()

    c.execute("SELECT trust, closeness, importance FROM social WHERE user_id=?", (user_id,))
    row = c.fetchone()

    if not row:
        c.execute("INSERT INTO social VALUES (?, ?, ?, ?)", (user_id, 0.5, 0.0, 0.5))
        conn.commit()
        conn.close()
        return {"trust": 0.5, "closeness": 0.0, "importance": 0.5}

    conn.close()

    return {
        "trust": row[0],
        "closeness": row[1],
        "importance": row[2]
    }


def update_social(user_id, text):

    social = get_social(user_id)

    trust = social["trust"]
    closeness = social["closeness"]

    if any(w in text for w in ["謝謝", "讚", "好"]):
        trust += 0.05

    if any(w in text for w in ["白癡", "幹", "滾"]):
        trust -= 0.15

    closeness += 0.03

    trust = max(0, min(1, trust))
    closeness = max(0, min(1, closeness))

    importance = (trust * 0.6) + (closeness * 0.4)

    conn = sqlite3.connect("memory.db")
    c = conn.cursor()

    c.execute("""
    INSERT OR REPLACE INTO social VALUES (?, ?, ?, ?)
    """, (user_id, trust, closeness, importance))

    conn.commit()
    conn.close()


# =========================
# 🧠 GEMINI CORE
# =========================
def ask_gemini(user_id, text, is_idle=False):

    social = get_social(user_id)
    memory = get_memory(user_id)

    mode = "主動插話" if is_idle else "回應使用者"

    prompt = f"""
你是一個在群組中的AI角色。

目前模式：{mode}

社會狀態：
- trust: {social['trust']}
- closeness: {social['closeness']}
- importance: {social['importance']}

最近記憶：
{memory}

規則：
- 如果是主動插話，要自然像突然想到
- 不要太頻繁講話
- 像真人在群組聊天
- 不要提到系統或AI

輸入：
{text}
"""

    return model.generate_content(prompt).text


# =========================
# 🔥 IDLE DETECTOR
# =========================
def check_idle_and_generate():

    now = time.time()

    if now - LAST_ACTIVE["group"] < IDLE_THRESHOLD:
        return None

    # 偽 user（代表群組）
    fake_user = "group"

    message = ask_gemini(fake_user, "群組現在很安靜，請自然講一句話", is_idle=True)

    return message


# =========================
# 🚀 SEND MESSAGE
# =========================
def send_message(text, chat_id):
    requests.post(f"{API}/sendMessage", json={
        "chat_id": chat_id,
        "text": text
    })


# =========================
# 🤖 WEBHOOK
# =========================
@app.route("/webhook", methods=["POST"])
def webhook():

    global LAST_ACTIVE

    data = request.get_json()

    if "message" in data:

        #測試
        print("📩 WEBHOOK HIT")

        chat_id = data["message"]["chat"]["id"]
        user_id = str(chat_id)
        text = data["message"].get("text", "")

        # 更新活躍時間
        LAST_ACTIVE["group"] = time.time()

        # 存記憶
        save_memory(user_id, text)

        # 社會狀態更新
        update_social(user_id, text)

        # 正常回覆
        reply = ask_gemini(user_id, text)

        #測試
        print("🤖 REPLY:", reply)

        send_message(reply, chat_id)

        #測試
        print("📤 SENDING MESSAGE")

    return "ok"


# =========================
# 🟡 EXTERNAL TRIGGER (給 cron 用)
# =========================
@app.route("/check_idle", methods=["GET"])
def check_idle():

    message = check_idle_and_generate()

    if message:
        # ⚠️ 這裡你要換成你的 group chat id
        GROUP_CHAT_ID = os.getenv("GROUP_CHAT_ID")

        send_message(message, GROUP_CHAT_ID)

        return "sent"

    return "no action"


# =========================
# 🟢 HOME
# =========================
@app.route("/")
def home():
    return "V7.5 Active NPC System running"


# =========================
# INIT DB
# =========================
init_db()