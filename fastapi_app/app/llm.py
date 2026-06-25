"""
llm.py  —  the LLM integration (Day 09 HTTP call + Day 10 streaming).

This is where the API talks to an LLM to SUMMARISE a product's reviews. It shows
the full real-world shape:
  - build a prompt from real data (the product's reviews),
  - POST to the OpenAI chat-completions endpoint with streaming turned on,
  - read the streamed 'data: ...' lines back and yield the text pieces as they
    arrive (an async generator — Day 10).

KEY DESIGN CHOICE — works with OR without an API key:
  If OPENAI_API_KEY is set, we call the real model and stream its answer.
  If it is NOT set, we fall back to a small local summariser so the endpoint
  STILL runs for every student. Same streaming interface either way — the rest
  of the app never needs to know which path ran.
"""
import os, json
import httpx

OPENAI_URL = "https://api.openai.com/v1/chat/completions"
MODEL = "gpt-4o-mini"


def _build_prompt(product_name: str, reviews: list[dict]) -> str:
    """Turn the real review rows into a single instruction for the model."""
    if not reviews:
        return f"There are no reviews yet for {product_name}. Say so in one sentence."
    lines = [f"- {r['rating']}/5: {r['title']}" for r in reviews]
    joined = "\n".join(lines)
    return (
        f"Summarise the customer reviews for '{product_name}' in 2-3 short sentences. "
        f"Mention the overall sentiment and any common themes.\n\nReviews:\n{joined}"
    )


async def stream_summary(product_name: str, reviews: list[dict]):
    """
    Async GENERATOR that yields the summary text in small pieces as it is produced.
    The caller (the SSE endpoint) wraps each piece in a 'data: ...' line.
    """
    api_key = os.getenv("OPENAI_API_KEY")

    # ---------- path A: no key -> local fallback (always works) ----------
    if not api_key:
        async for piece in _local_summary(product_name, reviews):
            yield piece
        return

    # ---------- path B: real LLM, streamed (Day 09 + Day 10) ----------
    prompt = _build_prompt(product_name, reviews)
    payload = {
        "model": MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "stream": True,                       # <- ask the API to STREAM the reply
    }
    headers = {"Authorization": f"Bearer {api_key}"}   # Day 09: the auth header

    async with httpx.AsyncClient(timeout=30.0) as client:
        # client.stream(...) keeps the connection open and lets us read line by line
        async with client.stream("POST", OPENAI_URL, json=payload, headers=headers) as resp:
            async for line in resp.aiter_lines():     # Day 10: async for over a stream
                print(line)
                if not line.startswith("data: "):
                    continue
                data = line[len("data: "):]
                if data.strip() == "[DONE]":          # OpenAI's end-of-stream marker
                    break
                try:
                    chunk = json.loads(data)
                    # the new text piece lives in choices[0].delta.content
                    piece = chunk["choices"][0]["delta"].get("content", "")
                    if piece:
                        yield piece
                except (json.JSONDecodeError, KeyError, IndexError):
                    continue                          # skip any keep-alive / odd line


async def _local_summary(product_name: str, reviews: list[dict]):
    """
    A tiny offline stand-in for the LLM so the feature runs with no API key.
    It computes the average rating and emits a sentence, word by word, with a
    small delay so you can SEE it stream just like the real model.
    """
    import asyncio
    if not reviews:
        text = f"There are no reviews yet for {product_name}."
    else:
        avg = sum(r["rating"] for r in reviews) / len(reviews)
        mood = "very positive" if avg >= 4.5 else "positive" if avg >= 3.5 else "mixed"
        themes = ", ".join(r["title"] for r in reviews[:3])
        text = (f"Customers are {mood} about {product_name} "
                f"(average {avg:.1f}/5 across {len(reviews)} reviews). "
                f"Common themes: {themes}.")
    # emit word by word to imitate token streaming
    for word in text.split(" "):
        yield word + " "
        await asyncio.sleep(0.05)
