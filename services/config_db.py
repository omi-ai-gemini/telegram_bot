import sqlite3
import os

DB_NAME = os.path.join("/tmp", "app.db")

def get_conn():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn