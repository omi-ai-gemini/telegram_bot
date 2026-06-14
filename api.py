from flask import request, jsonify
from services.database import get_conn


# =========================
# 新增 / 更新 bot
# =========================
@app.route("/api/bot", methods=["POST"])
def add_bot():

    data = request.json
    bot_id = data.get("bot_id")
    token = data.get("token")

    if not bot_id or not token:
        return jsonify({"error": "missing data"}), 400

    conn = get_conn()
    cursor = conn.cursor()

    cursor.execute("""
    INSERT INTO bot_config (bot_id, token)
    VALUES (%s, %s)
    ON CONFLICT (bot_id)
    DO UPDATE SET token = EXCLUDED.token
    """, (bot_id, token))

    conn.commit()
    conn.close()

    return jsonify({"status": "ok"})


# =========================
# 查詢所有 bot
# =========================
@app.route("/api/bot", methods=["GET"])
def get_bots():

    conn = get_conn()
    cursor = conn.cursor()

    cursor.execute("""
    SELECT bot_id, token FROM bot_config
    """)

    rows = cursor.fetchall()
    conn.close()

    return jsonify([
        {"bot_id": r[0], "token": r[1]}
        for r in rows
    ])


# =========================
# 新增 / 更新 user gemini key
# =========================
@app.route("/api/user", methods=["POST"])
def add_user():

    data = request.json
    user_id = data.get("user_id")
    gemini_key = data.get("gemini_key")

    if not user_id or not gemini_key:
        return jsonify({"error": "missing data"}), 400

    conn = get_conn()
    cursor = conn.cursor()

    cursor.execute("""
    INSERT INTO user_config (user_id, gemini_key)
    VALUES (%s, %s)
    ON CONFLICT (user_id)
    DO UPDATE SET gemini_key = EXCLUDED.gemini_key
    """, (user_id, gemini_key))

    conn.commit()
    conn.close()

    return jsonify({"status": "ok"})


# =========================
# 查詢所有 user
# =========================
@app.route("/api/user", methods=["GET"])
def get_users():

    conn = get_conn()
    cursor = conn.cursor()

    cursor.execute("""
    SELECT user_id, gemini_key FROM user_config
    """)

    rows = cursor.fetchall()
    conn.close()

    return jsonify([
        {"user_id": r[0], "gemini_key": r[1]}
        for r in rows
    ])