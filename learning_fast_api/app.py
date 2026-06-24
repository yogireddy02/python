# ============================================================
# ShopSmart API  -  Day 11 Reference (FastAPI)
# ============================================================
#
# WHAT THIS FILE TEACHES
# ----------------------
# A small-but-complete FastAPI service that shows, in one place:
#   1. Custom middleware (authentication + request timing)
#   2. Pydantic request/response models with validation
#   3. Self-documenting endpoints (Swagger / OpenAPI)
#   4. Proper error documentation (401 / 404 / 422)
#
# HOW A REQUEST TRAVELS THROUGH THE APP
# -------------------------------------
# Middleware wraps the app like nested layers. The request goes
# DOWN through each layer, hits the endpoint, then the response
# comes back UP through the same layers in reverse.
#
#   Client
#     |  HTTP Request
#     v
#   +--------------------+
#   | TimingMiddleware   |  (Before: start timer)
#   +--------------------+
#     |  call_next()
#     v
#   +--------------------+
#   | AuthMiddleware     |  (Before: check API key)
#   +--------------------+
#     |  call_next()
#     v
#   +--------------------+
#   | Router -> Endpoint |  (Your function runs here)
#   +--------------------+
#     |  return value
#     v
#   +--------------------+
#   | AuthMiddleware     |  (After)
#   +--------------------+
#     v
#   +--------------------+
#   | TimingMiddleware   |  (After: stop timer, add headers)
#   +--------------------+
#     v
#   Client receives response
#
# Mental model -> it is just nested function calls:
#   TimingMiddleware( AuthMiddleware( Endpoint ) )
#
# ============================================================


# ------------------------------------------------------------
# IMPORTS
# ------------------------------------------------------------
# Standard library
import time              # high-resolution timer for measuring latency
import uuid              # generate a unique ID per request
from enum import Enum    # used to define a fixed set of valid categories
from typing import List  # type hint for "a list of ProductOut"

# FastAPI gives us the app, routing, dependency-injection and
# helpers for documenting path parameters and security.
from fastapi import APIRouter, Depends, FastAPI, Path, Security
from fastapi.security import APIKeyHeader  # declares the X-API-Key scheme to OpenAPI

# Pydantic is the validation layer. Every request body is parsed
# into one of these models; invalid data is rejected with a 422.
from pydantic import BaseModel, ConfigDict, Field, field_validator

# Starlette is the ASGI toolkit FastAPI is built on. We use its
# primitives directly for middleware and raw responses.
from starlette import status                                  # named HTTP codes (status.HTTP_201_CREATED, ...)
from starlette.middleware.base import BaseHTTPMiddleware       # base class for writing middleware
from starlette.requests import Request                         # the incoming request object
from starlette.responses import JSONResponse                   # build a JSON response by hand (used for 401/404)


# ============================================================
# OpenAPI Tag Metadata
# ------------------------------------------------------------
# Tags group endpoints into sections in Swagger UI. Giving each
# tag a description adds a short intro paragraph under its header.
# Markdown (bold, tables, etc.) is rendered in the docs.
# ============================================================

TAGS_METADATA = [
    {
        "name": "Health",
        "description": "Public endpoints for service discovery and health "
        "checks. **No API key required.**",
    },
    {
        "name": "Products",
        "description": "Browse and manage the product catalog. "
        "**Every endpoint requires a valid `X-API-Key` header.** "
        "Use the **Authorize** button (top right) to set it once for "
        "all requests.",
    },
]


# ============================================================
# FastAPI Application
# ------------------------------------------------------------
# Everything passed here feeds the auto-generated OpenAPI schema,
# which Swagger UI (/docs) and ReDoc (/redoc) read to build the
# documentation pages. So "good docs" largely means "fill these in".
# ============================================================

app = FastAPI(
    title="ShopSmart API",                                  # shown as the page title in /docs
    summary="A teaching-grade Product API built with FastAPI.",  # one-line subtitle
    description="""
A small but complete **Product API** that demonstrates the building blocks
of a production FastAPI service.

### What this API shows you
- **API-key authentication** via custom middleware (see the lock icons).
- **Request timing** via middleware (`X-Request-ID`, `X-Process-Time` headers).
- **Request validation** with Pydantic models and field constraints.
- **Rich, self-documenting endpoints** powered by OpenAPI.

### Authentication
All `/products/*` endpoints require an `X-API-Key` header.

| Demo key          | Use for            |
|-------------------|--------------------|
| `demo-key-123`    | General testing    |
| `student-key-456` | Classroom exercises|

Click **Authorize** and paste one of the keys above to try the endpoints.
    """,                                                    # the big markdown blurb at the top of /docs
    version="1.0.0",                                        # your API version (shown in the docs header)
    openapi_tags=TAGS_METADATA,                             # the tag descriptions defined above
    contact={                                               # appears in the docs + machine-readable spec
        "name": "ShopSmart API Support",
        "email": "support@shopsmart.example",
    },
    license_info={"name": "MIT"},                           # license shown in the docs
    # swagger_ui_parameters tweaks the Swagger UI itself (not the schema).
    # persistAuthorization keeps the key you typed in "Authorize" after a reload.
    swagger_ui_parameters={"persistAuthorization": True},
)


# ============================================================
# Configuration
# ============================================================

# Paths that skip authentication. The docs pages and the schema
# must stay public, otherwise you could not even open Swagger.
PUBLIC_PATHS = {
    "/",
    "/health",
    "/docs",          # Swagger UI
    "/redoc",         # ReDoc
    "/openapi.json",  # the raw OpenAPI schema both docs pages load
}

# Demo API keys kept in code ONLY because this is a tutorial.
# In production these belong in a secret store (AWS Secrets Manager,
# Vault, a database, ...), never hard-coded in source control.
VALID_API_KEYS = {
    "demo-key-123",
    "student-key-456",
}

# Reusable header documentation. TimingMiddleware adds these two
# headers to every response; declaring them here lets us attach the
# same docs to multiple endpoints (see the `responses=` blocks below)
# without repeating ourselves.
TIMING_HEADERS = {
    "X-Request-ID": {
        "description": "Unique ID generated for this request (8 hex chars).",
        "schema": {"type": "string", "example": "a1b2c3d4"},
    },
    "X-Process-Time": {
        "description": "Total server processing time for the request.",
        "schema": {"type": "string", "example": "1.45ms"},
    },
}


# ============================================================
# Security Scheme (documentation only)
# ------------------------------------------------------------
# IMPORTANT DISTINCTION (worth a whiteboard moment):
#
#   * AuthMiddleware below is what ACTUALLY enforces the key.
#   * This APIKeyHeader is what makes the requirement VISIBLE in Swagger.
#
# Middleware is invisible to OpenAPI, so without this scheme Swagger
# would show no lock icon and "Try it out" would have no field to send
# the key. Declaring the scheme + attaching it as a router dependency
# makes Swagger:
#   1. draw a lock on protected endpoints,
#   2. render the "Authorize" button,
#   3. actually send the X-API-Key header when you click "Try it out".
#
# auto_error=False -> if the header is missing, DON'T raise here. We let
# AuthMiddleware return the 401 so there is exactly ONE rejection point
# (a pattern called "single source of truth" / defense in depth).
# ============================================================

api_key_header = APIKeyHeader(
    name="X-API-Key",          # the exact header name clients must send
    auto_error=False,          # missing key -> return None instead of raising; middleware handles it
    description="API key required for all /products endpoints. "
    "Demo keys: demo-key-123, student-key-456",
)


async def require_api_key(api_key: str = Security(api_key_header)) -> str:
    """Dependency that surfaces the API-key requirement to OpenAPI.

    It does NOT validate the key (AuthMiddleware does). Its only job is
    to attach the security scheme to an endpoint so the docs show the
    lock + Authorize box. `Security(...)` is like `Depends(...)` but also
    registers the scheme in the OpenAPI `securitySchemes` section.
    """
    return api_key


# ============================================================
# Middleware
# ------------------------------------------------------------
# A middleware subclasses BaseHTTPMiddleware and implements
# `dispatch`. The key line is `await call_next(request)`, which
# hands control to the NEXT layer (eventually your endpoint) and
# returns its response. Code BEFORE call_next runs on the way in;
# code AFTER it runs on the way out.
# ============================================================


class TimingMiddleware(BaseHTTPMiddleware):
    """Generate a request ID, measure latency, attach response headers.

    Runs OUTERMOST (registered last), so it is the first to see the
    request and the last to touch the response -> perfect for timing.
    """

    async def dispatch(self, request: Request, call_next):
        print("\n========== Timing Middleware START ==========")

        # --- BEFORE the endpoint runs ---
        request_id = uuid.uuid4().hex[:8]      # short unique id to trace this one request in the logs
        start_time = time.perf_counter()       # perf_counter = monotonic clock, best for measuring durations

        print(f"Request ID: {request_id}")
        print(f"Path: {request.url.path}")

        # Hand control down the stack (Auth -> Router -> Endpoint).
        # Everything below this line runs AFTER the endpoint returns.
        response = await call_next(request)

        # --- AFTER the endpoint ran ---
        elapsed_ms = (time.perf_counter() - start_time) * 1000  # seconds -> milliseconds

        # Attach our timing info so the client (and Swagger) can see it.
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Process-Time"] = f"{elapsed_ms:.2f}ms"

        print(
            f"[{request_id}] {request.method} {request.url.path} "
            f"-> {response.status_code} in {elapsed_ms:.2f} ms"
        )
        print("========== Timing Middleware END ==========\n")

        return response


class AuthMiddleware(BaseHTTPMiddleware):
    """Validate the X-API-Key header; reject unauthorized requests.

    Runs INNER (registered first), i.e. right before the router. If the
    key is bad it returns a 401 immediately and `call_next` is never
    called -> the endpoint never runs.
    """

    async def dispatch(self, request: Request, call_next):
        print("Entered Auth Middleware")
        path = request.url.path

        # Step 1: let public paths through untouched (docs, health, root,
        # and any static files). No key needed for these.
        if path in PUBLIC_PATHS or path.startswith("/static/"):
            print("Public endpoint detected. Skipping authentication.")
            return await call_next(request)

        # Step 2: read the key from the request header (None if absent).
        api_key = request.headers.get("X-API-Key")

        # Step 3: reject anything that is not a known key. Returning a
        # response here SHORT-CIRCUITS the stack -> the endpoint is skipped.
        if api_key not in VALID_API_KEYS:
            print("Authentication Failed")
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={"detail": "Missing or invalid X-API-Key header"},
            )

        print("Authentication Successful")

        # Step 4: key is valid -> continue to the endpoint.
        response = await call_next(request)
        print("Exited Auth Middleware")
        return response


# ============================================================
# Register Middleware
# ------------------------------------------------------------
# GOTCHA students always hit: order is REVERSE of what you'd expect.
# The LAST middleware registered is the OUTERMOST (runs first on the
# way in). So with the order below:
#
#   add_middleware(AuthMiddleware)    -> inner layer
#   add_middleware(TimingMiddleware)  -> outer layer (executes first)
#
# Request : Timing -> Auth -> Endpoint
# Response: Endpoint -> Auth -> Timing
#
# We want Timing on the outside so it measures the auth check too.
# ============================================================

app.add_middleware(AuthMiddleware)
app.add_middleware(TimingMiddleware)


# ============================================================
# Enums
# ============================================================


class ProductCategory(str, Enum):
    """The fixed set of categories a product may belong to.

    Subclassing `str` makes each member behave like its string value
    (JSON-friendly). Using an Enum as a field type gives you free
    validation: any value outside this set is rejected with a 422, and
    Swagger renders the field as a dropdown.
    """

    electronics = "Electronics"
    books = "Books"
    clothing = "Clothing"
    home = "Home & Kitchen"
    sports = "Sports"
    toys = "Toys"


# ============================================================
# Pydantic Models
# ------------------------------------------------------------
# Models define the SHAPE of data. FastAPI uses them two ways:
#   * as a parameter type  -> validate the incoming request body
#   * as `response_model`   -> filter/serialize the outgoing response
# Each `Field(...)` constraint becomes both a runtime check AND a line
# in the Swagger schema.
# ============================================================


class ProductIn(BaseModel):
    """Request body used when **creating** a product.

    Validation rules (all enforced automatically -> 422 on failure):
    - `name`     : 1-100 characters, not blank/whitespace-only
    - `category` : must be one of the ProductCategory values
    - `price`    : > 0 and <= 1,000,000 (rounded to 2 decimals)
    - `stock`    : >= 0 and <= 1,000,000 (defaults to 0)
    """

    # model_config carries Pydantic settings. json_schema_extra injects
    # a full example object into the schema, so Swagger pre-fills the
    # "Try it out" request body with something realistic.
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "name": "Wireless Mouse",
                    "category": "Electronics",
                    "price": 29.99,
                    "stock": 100,
                }
            ]
        }
    )

    # Field(...) with `...` (Ellipsis) means the field is REQUIRED.
    # min_length / max_length -> string length checks (violation = 422).
    name: str = Field(
        ...,
        min_length=1,
        max_length=100,
        title="Product Name",
        description="Display name of the product. Leading/trailing "
        "whitespace is stripped; cannot be blank.",
        examples=["Wireless Mouse"],   # per-field example shown in the schema
    )

    # Typing this as the Enum is what restricts it to known categories.
    category: ProductCategory = Field(
        ...,
        description="Product category. Must be one of the allowed values.",
        examples=["Electronics"],
    )

    # Numeric constraints: gt = greater-than, le = less-than-or-equal.
    price: float = Field(
        ...,
        gt=0,                # price must be strictly positive
        le=1_000_000,        # and not absurdly large
        description="Unit price in USD. Must be greater than 0. "
        "Stored rounded to 2 decimal places.",
        examples=[29.99],
    )

    # default=0 makes this OPTIONAL; ge = greater-than-or-equal.
    stock: int = Field(
        default=0,
        ge=0,                # stock can be 0 but never negative
        le=1_000_000,
        description="Units currently in stock. Defaults to 0.",
        examples=[100],
    )

    # field_validator runs AFTER the basic Field checks pass. Use it for
    # custom logic the Field constraints can't express. `@classmethod`
    # is required by Pydantic v2; raising ValueError -> a 422 for the user.
    @field_validator("name")
    @classmethod
    def name_must_not_be_blank(cls, v: str) -> str:
        cleaned = v.strip()                       # remove surrounding whitespace
        if not cleaned:                           # "   " would pass min_length but is still empty
            raise ValueError("name must not be empty or whitespace only")
        return cleaned                            # return the cleaned value -> what gets stored

    @field_validator("price")
    @classmethod
    def round_price(cls, v: float) -> float:
        return round(v, 2)                        # normalize 9.999 -> 10.0 so money is always 2 dp


class ProductOut(BaseModel):
    """Response body returned for a single product.

    Using this as `response_model` guarantees the API only ever returns
    these five fields, in this shape, no matter what the endpoint builds
    internally (a nice safety net against leaking extra data).
    """

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "id": 1,
                    "name": "Wireless Mouse",
                    "category": "Electronics",
                    "price": 29.99,
                    "stock": 100,
                }
            ]
        }
    )

    id: int = Field(..., description="Server-assigned unique product ID.", examples=[1])
    name: str = Field(..., description="Product display name.", examples=["Wireless Mouse"])
    category: str = Field(..., description="Product category.", examples=["Electronics"])
    price: float = Field(..., description="Unit price in USD.", examples=[29.99])
    stock: int = Field(..., description="Units in stock.", examples=[100])


class ErrorResponse(BaseModel):
    """Standard error envelope returned by the API on failure.

    Referencing this as a `model` in `responses=` documents the exact
    JSON shape clients should expect for 401 / 404 errors.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [{"detail": "Missing or invalid X-API-Key header"}]
        }
    )

    detail: str = Field(..., description="Human-readable error message.")


# ============================================================
# In-Memory "Database"
# ------------------------------------------------------------
# A plain dict standing in for a real database so the tutorial has no
# external dependencies. Keyed by product id for O(1) lookups. Because
# it lives in memory, all changes are LOST when the server restarts.
# ============================================================

PRODUCTS: dict[int, dict] = {
    1: {"id": 1, "name": "Wireless Mouse", "category": "Electronics", "price": 29.99, "stock": 100},
    2: {"id": 2, "name": "Mechanical Keyboard", "category": "Electronics", "price": 49.99, "stock": 50},
    3: {"id": 3, "name": "Python Crash Course", "category": "Books", "price": 19.99, "stock": 200},
}


def _next_product_id() -> int:
    # Naive auto-increment: one past the current max id. Fine for a demo;
    # a real DB would own this (auto-increment column / sequence).
    return (max(PRODUCTS) + 1) if PRODUCTS else 1


# ============================================================
# Router Definition
# ------------------------------------------------------------
# An APIRouter groups related endpoints. Settings here apply to EVERY
# route on the router, which is how we avoid repetition:
#   * prefix       -> all paths start with /products
#   * tags         -> all grouped under "Products" in the docs
#   * dependencies -> require_api_key runs on each route (adds the lock)
#   * responses    -> the shared 401 is documented once, not per-route
# ============================================================

product_router = APIRouter(
    prefix="/products",
    tags=["Products"],
    dependencies=[Depends(require_api_key)],   # attaches the security scheme to every product route
    responses={
        status.HTTP_401_UNAUTHORIZED: {
            "model": ErrorResponse,
            "description": "Missing or invalid `X-API-Key` header.",
        }
    },
)


# ============================================================
# Health / Root Endpoints  (registered on `app`, so NOT under /products)
# ============================================================


@app.get(
    "/",
    tags=["Health"],
    summary="API welcome message",                  # short label shown in the endpoint list
    response_description="A short welcome payload.", # describes the 200 response specifically
)
def home():
    """Public root endpoint. **No API key required.**"""
    # The docstring above becomes the endpoint's long description in Swagger.
    return {"message": "Welcome to ShopSmart API"}


@app.get(
    "/health",
    tags=["Health"],
    summary="Health check",
    response_description="Service status, suitable for load-balancer probes.",
    responses={
        # Document an explicit example for the 200 case.
        200: {
            "description": "Service is up.",
            "content": {"application/json": {"example": {"status": "UP"}}},
        }
    },
)
def health():
    """Liveness probe. Returns `UP` when the service is running."""
    return {"status": "UP"}


# ============================================================
# Product Endpoints
# ============================================================


@product_router.get(
    "",                                              # empty path + prefix -> matches exactly "/products"
    summary="List available product endpoints",
    response_description="A map of available product routes.",
)
def product_usage():
    """Discovery endpoint describing the available product routes."""
    return {
        "usage": [
            {"/products/list": "List all products"},
            {"/products/{product_id}": "Get a single product"},
            {"/products/insert": "Create a product"},
        ]
    }


@product_router.get(
    "/list",
    response_model=List[ProductOut],                 # response is validated/serialized as a list of ProductOut
    summary="List all products",
    response_description="The full product catalog.",
    responses={
        200: {
            "description": "List of all products in the catalog.",
            "headers": TIMING_HEADERS,               # document the X-Request-ID / X-Process-Time headers
        }
    },
)
def list_products():
    """Return **every** product in the catalog.

    In a real service this would be paginated. Here it returns the
    full in-memory catalog so you can see the response shape.
    """
    print("Executing list_products endpoint")
    return list(PRODUCTS.values())                   # dict values -> list; response_model enforces the shape


@product_router.get(
    "/{product_id}",                                 # {product_id} is a PATH PARAMETER captured below
    response_model=ProductOut,
    summary="Get a single product",
    response_description="The requested product.",
    responses={
        200: {"description": "Product found.", "headers": TIMING_HEADERS},
        404: {                                       # document the "not found" case explicitly
            "model": ErrorResponse,
            "description": "No product exists with the given ID.",
        },
    },
)
def get_product(
    # Path(...) documents and validates the URL parameter. ge=1 means the
    # id must be a positive integer; anything else (e.g. /products/0 or
    # /products/abc) is rejected with a 422 before this function runs.
    product_id: int = Path(
        ...,
        ge=1,
        title="Product ID",
        description="The unique ID of the product to fetch.",
        examples=[1],
    ),
):
    """Fetch a single product by its ID.

    Returns **404** if no product matches `product_id`.
    """
    print(f"Executing get_product endpoint: {product_id}")

    product = PRODUCTS.get(product_id)               # None if the id is not in our store
    if product is None:
        # We build the 404 by hand here. (Idiomatic FastAPI would
        # `raise HTTPException(404, ...)`; we use JSONResponse to mirror
        # the style used in AuthMiddleware and keep the lesson consistent.)
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"detail": f"Product {product_id} not found"},
        )
    return product


@product_router.post(
    "/insert",
    response_model=ProductOut,                       # what we send back
    status_code=status.HTTP_201_CREATED,             # 201 is the correct "resource created" code (default would be 200)
    summary="Create a new product",
    response_description="The newly created product, including its server-assigned ID.",
    responses={
        201: {"description": "Product created successfully.", "headers": TIMING_HEADERS},
        422: {                                       # FastAPI auto-adds 422; we enrich it with a concrete example
            "description": "Validation error - one or more fields are invalid.",
            "content": {
                "application/json": {
                    "example": {
                        "detail": [
                            {
                                "type": "greater_than",
                                "loc": ["body", "price"],
                                "msg": "Input should be greater than 0",
                            }
                        ]
                    }
                }
            },
        },
    },
)
def create_product(product: ProductIn):              # `product: ProductIn` -> FastAPI parses+validates the JSON body
    """Create a new product.

    The request body is validated against `ProductIn`. Common failures
    that return **422 Unprocessable Entity**:

    | Problem                | Field      |
    |------------------------|------------|
    | Missing / blank name   | `name`     |
    | Unknown category       | `category` |
    | `price` <= 0           | `price`    |
    | `stock` < 0            | `stock`    |
    """
    print("Executing create_product endpoint")

    # model_dump() -> turn the validated model into a plain dict.
    product_data = product.model_dump()
    new_id = _next_product_id()

    created_product = {
        "id": new_id,
        "name": product_data["name"],
        # `category` came in as a ProductCategory enum member. Store its
        # plain string value so the saved record is JSON-clean. (The
        # isinstance guard keeps this robust if the type ever changes.)
        "category": product_data["category"].value
        if isinstance(product_data["category"], ProductCategory)
        else product_data["category"],
        "price": product_data["price"],
        "stock": product_data["stock"],
    }

    PRODUCTS[new_id] = created_product               # "insert" into our in-memory store
    return created_product                           # response_model strips this down to ProductOut's fields


# ============================================================
# Register Routers
# ------------------------------------------------------------
# Until you include it, the router's routes are not part of the app.
# ============================================================

app.include_router(product_router)


# ============================================================
# Run
# ------------------------------------------------------------
#   uvicorn main:app --reload
#
# Swagger UI : http://localhost:8000/docs
# ReDoc      : http://localhost:8000/redoc
#
# Example request (note the required header):
#   curl -X GET http://localhost:8000/products/list \
#        -H "X-API-Key: demo-key-123"
# ============================================================