"""
main.py  —  the application: routers + middleware + Swagger metadata.

Run (recommended):  uvicorn app.main:app --reload
Docs:               http://localhost:8000/docs

You can ALSO just press the green Run button (or `python app/main.py`). The small
block right below makes that work — see the comment there for why it's needed.
"""

# ---------------------------------------------------------------------------
# MAKE THE RUN BUTTON WORK.
# When you run this file directly (python app/main.py / the green ▶ button),
# Python loads it as a lone script with no package, so the relative imports
# below (from .routers ...) fail with:
#     "attempted relative import with no known parent package"
# This guard runs FIRST, before those imports. If it detects direct execution,
# it hands off to uvicorn using the proper package path and stops this script —
# so the relative imports are only ever reached in the correct package context.
# ---------------------------------------------------------------------------
if __name__ == "__main__" and (__package__ is None or __package__ == ""):
    import os, sys, uvicorn
    # add the PARENT of the app/ folder to the path, so "app" is importable as a package
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    # Pass the app as an IMPORT STRING ("app.main:app") so uvicorn imports it as a
    # package — that's what makes the relative imports below work.
    # NOTE: reload=False here on purpose. The auto-reloader re-runs this file by
    # PATH in a child process, which would re-trigger the relative-import error.
    # For live reload while developing, use the terminal instead:
    #     uvicorn app.main:app --reload
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=False)
    sys.exit(0)

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.openapi.docs import get_swagger_ui_html, get_redoc_html
from .routers import products, reviews
from .middleware import TimingMiddleware, AuthMiddleware

# The title/description/version below become the Swagger documentation header.
# docs_url=None / redoc_url=None turns OFF the built-in (CDN-based) docs pages —
# we serve our OWN offline versions below so they render with no internet.
app = FastAPI(
    title="ShopSmart API",
    description="The product API you called in Days 09-10 — now built with FastAPI. "
                "GET/POST/PUT/DELETE products, nested reviews, and a live SSE feed.",
    version="1.0.0",
    docs_url=None,
    redoc_url=None,
)

# Serve the vendored Swagger/ReDoc JS+CSS from app/static at the URL /static.
# This is why the docs work OFFLINE / behind a firewall: the browser loads these
# files from YOUR server, not from an internet CDN.
import os
_STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
app.mount("/static", StaticFiles(directory=_STATIC_DIR), name="static")

# middleware applies to every request.
# ORDER MATTERS: add_middleware stacks like an onion — the LAST one added becomes
# the OUTERMOST layer (runs first on the way in, last on the way out). We want
# timing to wrap everything — including requests that auth rejects — so timing
# must be the OUTER layer. Therefore add auth FIRST, then timing LAST (outermost).
app.add_middleware(AuthMiddleware)     # inner: checks the API key (public paths pass)
app.add_middleware(TimingMiddleware)   # outermost: times EVERY request, even 401s

# mount the routers (their endpoints become part of the app)
app.include_router(products.router)
app.include_router(reviews.router)


@app.get("/", tags=["Meta"])
def root():
    """A friendly landing endpoint pointing at the docs."""
    return {"service": "ShopSmart API", "docs": "/docs", "version": "1.0.0"}


@app.get("/health", tags=["Meta"])
def health():
    """Health check — used by load balancers and uptime monitors."""
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# OFFLINE docs: serve Swagger UI and ReDoc using our OWN vendored JS/CSS.
# These replace the built-in pages (which we turned off with docs_url=None).
# Because the *_js_url / *_css_url point at /static on this server, the docs
# render with no internet connection and through any firewall.
# ---------------------------------------------------------------------------
@app.get("/docs", include_in_schema=False)
def swagger_docs():
    return get_swagger_ui_html(
        openapi_url="/openapi.json",
        title="ShopSmart API — Swagger UI",
        swagger_js_url="/static/swagger-ui-bundle.js",
        swagger_css_url="/static/swagger-ui.css",
        swagger_favicon_url="/static/favicon.png",
    )


@app.get("/redoc", include_in_schema=False)
def redoc_docs():
    return get_redoc_html(
        openapi_url="/openapi.json",
        title="ShopSmart API — ReDoc",
        redoc_js_url="/static/redoc.standalone.js",
        redoc_favicon_url="/static/favicon.png",
    )
