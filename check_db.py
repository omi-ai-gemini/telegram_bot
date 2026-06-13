import sqlite3

conn = sqlite3.connect("app.db")
cursor = conn.cursor()

print("BOT")
for row in cursor.execute("SELECT * FROM bot_config"):
    print(row)

print("USER")
for row in cursor.execute("SELECT * FROM user_config"):
    print(row)

conn.close()