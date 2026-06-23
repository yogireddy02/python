# ShopSmart API — Day 11 (FastAPI)

The server side of the API you have been *calling* all through Days 09–10.
Now you BUILD it: GET/POST/PUT/DELETE products, reviews, an SSE live feed,
middleware, and auto-generated Swagger docs.

## Run it
```bash
pip install -r requirements.txt
uvicorn app.main:app --reload
```
You can also just press the green Run button on app/main.py (a guard at the top
of the file makes direct execution work — no ImportError).

## AI review summary (LLM + SSE)
Stream an AI-generated summary of a product's reviews:
```bash
curl -N -H "X-API-Key: demo-key-123" \
     http://localhost:8000/products/101/reviews/summary
```
Set OPENAI_API_KEY to use the real model (gpt-4o-mini); without it, a local
summary streams instead, so the endpoint always works.

## Auth
Most endpoints need an API key header:  `X-API-Key: demo-key-123`
Public paths (no key needed): `/`, `/health`, `/docs`, `/redoc`, `/openapi.json`
In Swagger (/docs) click "Authorize" or add the header; from code:
```python
httpx.get("http://localhost:8000/products", headers={"X-API-Key": "demo-key-123"})
```

Then open:
- http://localhost:8000/docs    ← Swagger UI (interactive, auto-generated)
- http://localhost:8000/redoc   ← alternative docs
- http://localhost:8000/products


## Opening the docs in your browser
1. Start the server (keep the terminal open):
   ```
   uvicorn app.main:app --reload
   ```
2. In your browser, go to:  http://localhost:8000/docs   (Swagger UI)
   or                        http://localhost:8000/redoc  (ReDoc)

These docs work OFFLINE and behind firewalls: the Swagger/ReDoc JavaScript and CSS
are served from this project (app/static/), not from an internet CDN. If you ever
see a BLANK docs page in other projects, that is almost always the CDN being blocked.

## What each file teaches
- app/contracts.py   — the CONTRACT (Pydantic request/response models)
- app/database.py    — a tiny in-memory DB stand-in (swap for Postgres later)
- app/routers/products.py — GET/POST/PUT/DELETE (client → response, DB update)
- app/routers/reviews.py  — nested resource + SSE live feed + AI summary stream
- app/llm.py         — the LLM call (real OpenAI streaming, or local fallback)
- app/middleware.py  — middleware (runs on every request): timing + request id, AND auth
- app/main.py        — wires routers + middleware + Swagger metadata together
