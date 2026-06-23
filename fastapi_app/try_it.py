"""
try_it.py  —  call your own ShopSmart API (start the server first).

    Terminal 1:  uvicorn app.main:app --reload
    Terminal 2:  python try_it.py

This uses httpx exactly like Days 09-10 — but now the server is YOURS.
"""
import httpx

BASE = "http://localhost:8000"
# protected endpoints need an API key (public ones like /docs do not)
HEADERS = {"X-API-Key": "demo-key-123"}

print("List products:")
for p in httpx.get(f"{BASE}/products", headers=HEADERS).json():
    print(f"  #{p['id']}  {p['name']:<20} ${p['price']}")

print("\nCreate a product (POST):")
new = httpx.post(f"{BASE}/products",
                 json={"name": "Desk Lamp", "category": "Home", "price": 24.5, "stock": 10},
                 headers=HEADERS)
print("  status:", new.status_code, "-> new id", new.json()["id"])

print("\nUpdate it (PUT):")
pid = new.json()["id"]
upd = httpx.put(f"{BASE}/products/{pid}", json={"price": 19.99}, headers=HEADERS)
print("  new price:", upd.json()["price"])

print("\nAdd a review (POST nested):")
rev = httpx.post(f"{BASE}/products/101/reviews", json={"rating": 5, "title": "Love it"}, headers=HEADERS)
print("  status:", rev.status_code, "->", rev.json())

print("\nDelete the product (DELETE):")
d = httpx.delete(f"{BASE}/products/{pid}", headers=HEADERS)
print("  ", d.json())

print("\nTip: open http://localhost:8000/docs to try every endpoint in Swagger.")
print("Tip: live SSE feed -> curl -N http://localhost:8000/reviews/stream")

print("\nAI review summary (streamed over SSE):")
with httpx.stream("GET", f"{BASE}/products/101/reviews/summary", headers=HEADERS) as s:
    import json as _json
    for line in s.iter_lines():
        if line.startswith("data: "):
            try:
                piece = _json.loads(line[6:]).get("text", "")
                print(piece, end="", flush=True)
            except Exception:
                pass
    print()
print("Tip: set OPENAI_API_KEY to use the real model; otherwise a local summary streams.")
