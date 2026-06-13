from services.database import get_conn

def test_connection():
    try:
        conn = get_conn()
        cursor = conn.cursor()

        cursor.execute("SELECT 1")
        result = cursor.fetchone()

        print("✔ Supabase 連線成功：", result)

        conn.close()

    except Exception as e:
        print("❌ Supabase 連線失敗：", e)


if __name__ == "__main__":
    test_connection()