"""
database.py  —  a tiny in-memory 'database'.

For the tutorial we keep data in plain Python dicts so the project runs with zero
setup. The functions below mimic real DB operations (SELECT / INSERT / UPDATE /
DELETE). On Day 08 you saw the real psycopg2 / asyncpg versions — swapping this
file for those is all it takes to go to a real Postgres.

Each function returns plain dicts; the router turns them into contract objects.
"""
from itertools import count
import asyncio

# seed data (acts like a 'products' table)
_PRODUCTS = {
    101: {"id": 101, "name": "Classic Monitor",    "category": "Electronics", "price": 205.21, "stock": 34},
    102: {"id": 102, "name": "Wireless Mouse",     "category": "Electronics", "price": 29.99,  "stock": 120},
    103: {"id": 103, "name": "Yoga Mat Pro",       "category": "Sports",      "price": 45.00,  "stock": 60},
}
_REVIEWS: dict[int, list[dict]] = {
    101: [{"product_id": 101, "rating": 5, "title": "Crisp display"}],
}
_id_seq = count(start=104)   # new product ids start at 104

# a list of asyncio.Queues — one per connected SSE listener (used in reviews.py)
review_subscribers: list[asyncio.Queue] = []


# ---------- products: the four basic operations (Day 08 CRUD) ----------
def list_products(category: str | None = None) -> list[dict]:
    rows = list(_PRODUCTS.values())
    if category:
        rows = [p for p in rows if p["category"].lower() == category.lower()]
    return rows

def get_product(product_id: int) -> dict | None:
    return _PRODUCTS.get(product_id)

def insert_product(data: dict) -> dict:
    new_id = next(_id_seq)
    row = {"id": new_id, **data}
    _PRODUCTS[new_id] = row
    return row

def update_product(product_id: int, changes: dict) -> dict | None:
    row = _PRODUCTS.get(product_id)
    if row is None:
        return None
    # only overwrite the fields the client actually sent
    for key, value in changes.items():
        if value is not None:
            row[key] = value
    return row

def delete_product(product_id: int) -> bool:
    return _PRODUCTS.pop(product_id, None) is not None


# ---------- reviews (nested under a product) ----------
def get_reviews(product_id: int) -> list[dict]:
    return _REVIEWS.get(product_id, [])

async def add_review(product_id: int, review: dict) -> dict:
    row = {"product_id": product_id, **review}
    _REVIEWS.setdefault(product_id, []).append(row)
    # notify every SSE listener that a new review arrived
    for q in review_subscribers:
        await q.put(row)
    return row
