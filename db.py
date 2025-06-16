import mysql.connector

def get_db_connection():
    try:
        conn = mysql.connector.connect(
            host="localhost",
            user="root",
            password="WJ28@krhps",
            database="csesa_db"
        )
        print("[OK] DB connection successful")
        return conn
    except mysql.connector.Error as err:
        print(f"[ERROR] DB connection failed: {err}")
        raise
