import sqlite3

conn = sqlite3.connect("app.db")
cursor = conn.cursor()

bot_id = "omiA"
token = "8499475130:AAEmiYYWJ6MjqUp8A1ORFfkxBNx9atqGvSM"

# BOT
cursor.execute("""
INSERT OR REPLACE INTO bot_config
(bot_id, token)
VALUES (?, ?)
""", (
    bot_id,
    token
))

conn.commit()
conn.close()

print("OK")