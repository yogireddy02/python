"""
middleware.py  —  MIDDLEWARE runs on EVERY request, around your endpoints.

Think of it as a checkpoint every request passes through on the way IN and the
response passes through on the way OUT. Common uses: logging, timing, adding
headers, auth checks. Here we:
  - give each request a short id,
  - measure how long it took,
  - add both as response headers (X-Request-ID, X-Process-Time).
"""
import time, uuid
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request


# ===========================================================================
# HOW MIDDLEWARE WORKS: the dispatch method and call_next
# ===========================================================================
# When you subclass BaseHTTPMiddleware, Starlette calls ONE method of yours for
# every request: dispatch(). You don't pick that name — it's the method the base
# class looks for. Overriding it is what makes your code a checkpoint.
#
#     async def dispatch(self, request, call_next):
#       |          |        |          |
#       |          |        |          +-- "run the REST of the chain and give
#       |          |        |              me back the response" (the inner
#       |          |        |              middleware + your endpoint)
#       |          |        +-- the incoming request, BEFORE any endpoint sees it
#       |          +-- the method name Starlette calls, once per request
#       +-- must be async: it awaits call_next (middleware lives in the async path)
#
# call_next is the hinge between "on the way IN" and "on the way OUT":
#
#     async def dispatch(self, request, call_next):
#         # ... code here runs on the way IN (endpoint hasn't run yet)
#         response = await call_next(request)   # hand off inward; endpoint runs
#         # ... code here runs on the way OUT (response is coming back)
#         return response
#
# And because YOU decide whether to call it, a middleware can STOP a request:
# return a response WITHOUT calling call_next (see AuthMiddleware's 401 below)
# and the endpoint never runs. That is the whole mechanism of a guard.
# ===========================================================================


class TimingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # ----- on the way IN -----
        request_id = uuid.uuid4().hex[:8]
        start = time.perf_counter()

        # hand control to the actual endpoint (and any inner middleware)
        response = await call_next(request)

        # ----- on the way OUT -----
        elapsed_ms = (time.perf_counter() - start) * 1000
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Process-Time"] = f"{elapsed_ms:.1f}ms"
        # a tiny server-side log line
        print(f"[{request_id}] {request.method} {request.url.path} -> "
              f"{response.status_code} in {elapsed_ms:.1f}ms")
        return response


# ---------------------------------------------------------------------------
# AuthMiddleware — runs on EVERY request, but lets PUBLIC paths through.
#
# The lesson: "auth on every request" does NOT mean "auth on every path". You
# always keep a few paths open — the docs, health check, and root — or you lock
# yourself out of your own API. So the middleware runs each time, looks at the
# path, and decides: public -> pass through; everything else -> require a key.
# ---------------------------------------------------------------------------
from starlette.responses import JSONResponse

# paths anyone may hit without a key (docs, health, the landing page)
PUBLIC_PATHS = {"/", "/health", "/docs", "/redoc", "/openapi.json"}

# in a real app this lives in a database / secret manager, NEVER in code
VALID_API_KEYS = {"demo-key-123", "student-key-456"}


class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        path = request.url.path

        # 1) public paths skip auth entirely.
        #    Note the /static check: the docs PAGE is public, but so are the JS/CSS
        #    files it loads — miss those and the page renders blank (401'd assets).
        if path in PUBLIC_PATHS or path.startswith("/static/"):
            return await call_next(request)

        # 2) everyone else must present a valid X-API-Key header
        api_key = request.headers.get("X-API-Key")
        if api_key not in VALID_API_KEYS:
            # 401 Unauthorized — stop here, the endpoint never runs
            return JSONResponse(
                status_code=401,
                content={"detail": "Missing or invalid X-API-Key header"},
            )

        # 3) key is good -> let the request continue to the endpoint
        return await call_next(request)
