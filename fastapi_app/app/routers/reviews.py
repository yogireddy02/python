"""
routers/reviews.py  —  reviews (a nested resource) + a live SSE feed.

Two ideas here:
  1) NESTED RESOURCE: reviews live under a product:  /products/{id}/reviews
  2) SSE (Server-Sent Events): a long-lived GET that STREAMS new reviews to the
     client as they happen — the same 'data: ...' format you saw receiving from
     OpenAI on Day 09, now produced by YOUR server.
"""
import asyncio, json
from fastapi import APIRouter, HTTPException, Header
from fastapi.responses import StreamingResponse
from .. import database as db
from .. import llm
from ..contracts import ReviewIn, ReviewOut

router = APIRouter(tags=["Reviews"])


@router.get("/products/{product_id}/reviews", response_model=list[ReviewOut])
def list_reviews(product_id: int,x_api_key: str = Header(...)):
    """All reviews for one product."""
    if db.get_product(product_id) is None:
        raise HTTPException(status_code=404, detail=f"Product {product_id} not found")
    return db.get_reviews(product_id)


@router.post("/products/{product_id}/reviews", response_model=ReviewOut, status_code=201)
async def add_review(product_id: int, review: ReviewIn,x_api_key: str = Header(...)):
    """
    Add a review (rating 1-5, enforced by the contract). This also PUSHES the new
    review to every client currently listening on the SSE stream below.
    """
    if db.get_product(product_id) is None:
        raise HTTPException(status_code=404, detail=f"Product {product_id} not found")
    return await db.add_review(product_id, review.model_dump())


@router.get("/reviews/stream")
async def stream_reviews(x_api_key: str = Header(...)):
    """
    SSE live feed. Open this in one terminal:
        curl -N http://localhost:8000/reviews/stream
    then POST a review in another — you'll see it appear instantly here.

    The server keeps the connection open and yields one 'data: {...}' line per
    new review. async generators (Day 10) make this clean.
    """
    queue: asyncio.Queue = asyncio.Queue()
    db.review_subscribers.append(queue)        # register this listener

    async def event_stream():
        try:
            # tell the client we're connected
            yield "event: ready\ndata: listening for new reviews\n\n"
            while True:
                review = await queue.get()      # wait for the next new review
                yield f"data: {json.dumps(review)}\n\n"   # SSE line format
        finally:
            db.review_subscribers.remove(queue)  # clean up when client disconnects

    # media_type text/event-stream is what makes it an SSE response
    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.get("/products/{product_id}/reviews/summary")
async def summarise_reviews(product_id: int,x_api_key: str = Header(...)):
    """
    AI-generated summary of a product's reviews, STREAMED over SSE.

    This is the capstone: it pulls the product's real reviews, sends them to an
    LLM, and streams the summary back word-by-word as it is generated — the same
    'data: ...' format as the live feed above.

        curl -N -H "X-API-Key: demo-key-123" \\
             http://localhost:8000/products/101/reviews/summary

    Works with no API key too: without OPENAI_API_KEY it streams a local summary
    instead, so the endpoint always runs. (Set OPENAI_API_KEY to use the real model.)
    """
    product = db.get_product(product_id)
    if product is None:
        raise HTTPException(status_code=404, detail=f"Product {product_id} not found")

    reviews = db.get_reviews(product_id)

    async def event_stream():
        # stream each text piece from the LLM as its own SSE 'data:' line
        async for piece in llm.stream_summary(product["name"], reviews):
            yield f"data: {json.dumps({'text': piece})}\n\n"
        # a final marker so the client knows the summary is complete
        yield "event: done\ndata: end\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")
