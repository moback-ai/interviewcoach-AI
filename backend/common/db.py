import os
import psycopg2
import psycopg2.extras
from dotenv import load_dotenv

load_dotenv(dotenv_path=os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env"))

def get_db():
    return psycopg2.connect(
        host=os.getenv("DB_HOST", "localhost"),
        port=int(os.getenv("DB_PORT", 5432)),
        dbname=os.getenv("DB_NAME", "interview_db"),
        user=os.getenv("DB_USER", "interview_user"),
        password=os.getenv("DB_PASSWORD"),
        cursor_factory=psycopg2.extras.RealDictCursor
    )

def query_one(sql, params=None):
    conn = get_db()
    try:
        cur = conn.cursor()
        cur.execute(sql, params or ())
        return cur.fetchone()
    finally:
        conn.close()

def query_all(sql, params=None):
    conn = get_db()
    try:
        cur = conn.cursor()
        cur.execute(sql, params or ())
        return cur.fetchall()
    finally:
        conn.close()

def execute(sql, params=None):
    """Run INSERT/UPDATE/DELETE and return the first row if RETURNING is used"""
    conn = get_db()
    try:
        cur = conn.cursor()
        cur.execute(sql, params or ())
        result = None
        try:
            result = cur.fetchone()
        except Exception:
            pass
        conn.commit()
        return result
    finally:
        conn.close()
