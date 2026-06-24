"""
database.py  —  a tiny in-memory 'database'.

For the tutorial we keep data in plain Python dicts so the project runs with zero
setup. The functions below mimic real DB operations (SELECT / INSERT / UPDATE /
DELETE). On Day 08 you saw the real psycopg2 / asyncpg versions — swapping this
file for those is all it takes to go to a real Postgres.

Each function returns plain dicts; the router turns them into contract objects.
"""

import os
import psycopg2
import psycopg2.extras
from dotenv import load_dotenv

load_dotenv()   # reads .env file into os.environ


def get_connection():
    """
    Open a connection to PostgreSQL using credentials from .env
    Always use inside a try/finally or with block to ensure it closes.
    """
    return psycopg2.connect(
        host    = os.environ.get('DB_HOST', 'localhost'),
        port    = int(os.environ.get('DB_PORT', '5432')),
        dbname  = os.environ.get('DB_NAME'),
        user    = os.environ.get('DB_USER'),
        password= os.environ.get('DB_PASSWORD'),
    )


# Test the connection
try:
    conn = get_connection()
    print('Connected to PostgreSQL')
    print('DB name:', conn.get_dsn_parameters().get('dbname'))
    conn.close()
except Exception as e:
    print(f'Connection failed: {e}')
    print('Check your .env file — DB_HOST, DB_NAME, DB_USER, DB_PASSWORD')




# ---------- products: the four basic operations (Day 08 CRUD) ----------
def list_products(category: str | None = None) -> list[dict]:
    pass

def get_product(product_id: int) -> dict | None:
    pass

def insert_product(data: dict) -> dict:
    pass

def update_product(product_id: int, changes: dict) -> dict | None:
    pass

def delete_product(product_id: int) -> bool:
    pass


# ---------- reviews (nested under a product) ----------
def get_reviews(product_id: int) -> list[dict]:
    pass

async def add_review(product_id: int, review: dict) -> dict:
    pass
