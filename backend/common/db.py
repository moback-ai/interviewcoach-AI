import os
import psycopg2
import psycopg2.pool
import psycopg2.extras
from dotenv import load_dotenv

load_dotenv(dotenv_path=os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env"))

_pool = None


def _get_pool():
    global _pool
    if _pool is None:
        _pool = psycopg2.pool.ThreadedConnectionPool(
            minconn=int(os.getenv("DB_POOL_MIN", 2)),
            maxconn=int(os.getenv("DB_POOL_MAX", 20)),
            host=os.getenv("DB_HOST", "localhost"),
            port=int(os.getenv("DB_PORT", 5432)),
            dbname=os.getenv("DB_NAME", "interview_db"),
            user=os.getenv("DB_USER", "interview_user"),
            password=os.getenv("DB_PASSWORD"),
            cursor_factory=psycopg2.extras.RealDictCursor,
        )
    return _pool


def _get_conn():
    return _get_pool().getconn()


def _put_conn(conn):
    try:
        _get_pool().putconn(conn)
    except Exception:
        pass


def query_one(sql, params=None):
    conn = _get_conn()
    try:
        cur = conn.cursor()
        cur.execute(sql, params or ())
        return cur.fetchone()
    except Exception:
        conn.rollback()
        raise
    finally:
        _put_conn(conn)


def query_all(sql, params=None):
    conn = _get_conn()
    try:
        cur = conn.cursor()
        cur.execute(sql, params or ())
        return cur.fetchall()
    except Exception:
        conn.rollback()
        raise
    finally:
        _put_conn(conn)


def execute(sql, params=None):
    """Run INSERT/UPDATE/DELETE and return the first row if RETURNING is used."""
    conn = _get_conn()
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
    except Exception:
        conn.rollback()
        raise
    finally:
        _put_conn(conn)


def execute_many(sql, params_list):
    """Run the same SQL for a list of param tuples in a single transaction."""
    conn = _get_conn()
    try:
        cur = conn.cursor()
        cur.executemany(sql, params_list)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        _put_conn(conn)


def close_pool():
    """Gracefully close all pooled connections (call on app shutdown)."""
    global _pool
    if _pool:
        _pool.closeall()
        _pool = None
