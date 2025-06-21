import mysql.connector
import os
from dotenv import load_dotenv
load_dotenv()

def get_db_connection():
    try:
        conn = mysql.connector.connect(
            host=os.getenv("DB_HOST"),
            port=os.getenv("DB_PORT"),
            user=os.getenv("DB_USER"),
            password=os.getenv("DB_PASSWORD"),
            database=os.getenv("DB_NAME")
        )
        print("[OK] DB connection successful")
        return conn
    except mysql.connector.Error as err:
        print(f"[ERROR] DB connection failed: {err}")
        raise
