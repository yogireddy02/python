# ============================================================
# ShopSmart API
# ============================================================
#
# REQUEST FLOW
# ============================================================
#
# Client
#   |
#   | HTTP Request
#   v
# +--------------------+
# | TimingMiddleware   |  (Before Logic)
# +--------------------+
#          | call_next()
#          v
# +--------------------+
# | AuthMiddleware     |  (Before Logic)
# +--------------------+
#          | call_next()
#          v
# +--------------------+
# | Router Resolution  |
# +--------------------+
#          v
# +--------------------+
# | Endpoint Function  |
# +--------------------+
#          | Return Response
#          v
# +--------------------+
# | AuthMiddleware     |  (After Logic)
# +--------------------+
#          v
# +--------------------+
# | TimingMiddleware   |  (After Logic)
# +--------------------+
#          v
# Client receives response
#
# Request Path : Client -> Timing -> Auth -> Router -> Endpoint
# Response Path: Endpoint -> Auth -> Timing -> Client
#
# Middleware behaves like nested wrappers:
#   TimingMiddleware( AuthMiddleware( Endpoint ) )
#
# ============================================================

import time
import uuid
from enum import Enum
from typing import List

from fastapi import APIRouter, Depends, FastAPI, Path, Security
from fastapi.security import APIKeyHeader
from pydantic import BaseModel, ConfigDict, Field, field_validator
from starlette import status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

# ============================================================
# OpenAPI Tag Metadata
# ------------------------------------------------------------
# These descriptions render as section headers + intro text
# inside Swagger UI (/docs) and ReDoc (/redoc).
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
# ============================================================

app = FastAPI(
    title="ShopSmart API",
    summary="A teaching-grade Product API built with FastAPI.",
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
    """,
    version="1.0.0",
    openapi_tags=TAGS_METADATA,
    contact={
        "name": "ShopSmart API Support",
        "email": "support@shopsmart.example",
    },
    license_info={"name": "MIT"},
    # Keep the key you type in "Authorize" across page reloads.
    swagger_ui_parameters={"persistAuthorization": True},
)

# ============================================================
# Configuration
# ============================================================

# Endpoints that do NOT require authentication.
PUBLIC_PATHS = {
    "/",
    "/health",
    "/docs",
    "/redoc",
    "/openapi.json",
}

# Demo API keys.
# In production store these in AWS Secrets Manager, Vault, a DB, etc.
VALID_API_KEYS = {
    "demo-key-123",
    "student-key-456",
}

# Reusable header documentation for Swagger.
# These headers are added by TimingMiddleware on every response.
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
# Security Scheme (for Swagger documentation)
# ------------------------------------------------------------
# AuthMiddleware is what actually ENFORCES the API key on every
# request. But middleware is invisible to OpenAPI, so Swagger
# would show no lock icon and no way to send the key.
#
# Declaring this APIKeyHeader scheme + attaching it as a router
# dependency makes Swagger:
#   1. show a lock icon on protected endpoints,
#   2. render the "Authorize" button,
#   3. send the X-API-Key header on "Try it out".
#
# auto_error=False -> we let AuthMiddleware return the 401, so we
# have a single, consistent source of rejection (defense in depth).
# ============================================================

api_key_header = APIKeyHeader(
    name="X-API-Key",
    auto_error=False,
    description="API key required for all /products endpoints. "
    "Demo keys: demo-key-123, student-key-456",
)


async def require_api_key(api_key: str = Security(api_key_header)) -> str:
    """Surface the API-key requirement to OpenAPI/Swagger.

    Enforcement is handled by AuthMiddleware; this dependency only
    exists so the documentation shows the lock + Authorize box.
    """
    return api_key


# ============================================================
# Middleware
# ============================================================


class TimingMiddleware(BaseHTTPMiddleware):
    """Generate a request ID, measure latency, attach response headers."""

    async def dispatch(self, request: Request, call_next):
        print("\n========== Timing Middleware START ==========")

        request_id = uuid.uuid4().hex[:8]
        start_time = time.perf_counter()

        print(f"Request ID: {request_id}")
        print(f"Path: {request.url.path}")

        response = await call_next(request)

        elapsed_ms = (time.perf_counter() - start_time) * 1000

        response.headers["X-Request-ID"] = request_id
        response.headers["X-Process-Time"] = f"{elapsed_ms:.2f}ms"

        print(
            f"[{request_id}] {request.method} {request.url.path} "
            f"-> {response.status_code} in {elapsed_ms:.2f} ms"
        )
        print("========== Timing Middleware END ==========\n")

        return response


class AuthMiddleware(BaseHTTPMiddleware):
    """Validate the X-API-Key header; reject unauthorized requests."""

    async def dispatch(self, request: Request, call_next):
        print("Entered Auth Middleware")
        path = request.url.path

        # Step 1: allow public endpoints (and static files).
        if path in PUBLIC_PATHS or path.startswith("/static/"):
            print("Public endpoint detected. Skipping authentication.")
            return await call_next(request)

        # Step 2: extract API key.
        api_key = request.headers.get("X-API-Key")

        # Step 3: validate API key.
        if api_key not in VALID_API_KEYS:
            print("Authentication Failed")
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={"detail": "Missing or invalid X-API-Key header"},
            )

        print("Authentication Successful")

        # Step 4: continue request processing.
        response = await call_next(request)
        print("Exited Auth Middleware")
        return response


# ============================================================
# Register Middleware
# ------------------------------------------------------------
# The LAST registered middleware runs FIRST on the way in.
#   add_middleware(AuthMiddleware)    -> inner
#   add_middleware(TimingMiddleware)  -> outer (runs first)
#
# Request : Timing -> Auth -> Endpoint
# Response: Endpoint -> Auth -> Timing
# ============================================================

app.add_middleware(AuthMiddleware)
app.add_middleware(TimingMiddleware)

# ============================================================
# Enums
# ============================================================


class ProductCategory(str, Enum):
    """Allowed product categories.

    Using an Enum gives you free validation: any value outside this
    set is rejected with a 422, and Swagger renders a dropdown.
    """

    electronics = "Electronics"
    books = "Books"
    clothing = "Clothing"
    home = "Home & Kitchen"
    sports = "Sports"
    toys = "Toys"


# ============================================================
# Pydantic Models
# ============================================================


class ProductIn(BaseModel):
    """Request body used when **creating** a product.

    Validation rules (all enforced automatically -> 422 on failure):
    - `name`     : 1-100 characters, not blank/whitespace-only
    - `category` : must be one of the ProductCategory values
    - `price`    : > 0 and <= 1,000,000 (rounded to 2 decimals)
    - `stock`    : >= 0 and <= 1,000,000 (defaults to 0)
    """

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

    name: str = Field(
        ...,
        min_length=1,
        max_length=100,
        title="Product Name",
        description="Display name of the product. Leading/trailing "
        "whitespace is stripped; cannot be blank.",
        examples=["Wireless Mouse"],
    )

    category: ProductCategory = Field(
        ...,
        description="Product category. Must be one of the allowed values.",
        examples=["Electronics"],
    )

    price: float = Field(
        ...,
        gt=0,
        le=1_000_000,
        description="Unit price in USD. Must be greater than 0. "
        "Stored rounded to 2 decimal places.",
        examples=[29.99],
    )

    stock: int = Field(
        default=0,
        ge=0,
        le=1_000_000,
        description="Units currently in stock. Defaults to 0.",
        examples=[100],
    )

    @field_validator("name")
    @classmethod
    def name_must_not_be_blank(cls, v: str) -> str:
        cleaned = v.strip()
        if not cleaned:
            raise ValueError("name must not be empty or whitespace only")
        return cleaned

    @field_validator("price")
    @classmethod
    def round_price(cls, v: float) -> float:
        return round(v, 2)


class ProductOut(BaseModel):
    """Response body returned for a single product."""

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
    """Standard error envelope returned by the API on failure."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [{"detail": "Missing or invalid X-API-Key header"}]
        }
    )

    detail: str = Field(..., description="Human-readable error message.")


# ============================================================
# In-Memory "Database"
# ------------------------------------------------------------
# A simple dict standing in for a real database, so the endpoints
# can return realistic data and a genuine 404 when an ID is missing.
# ============================================================

PRODUCTS: dict[int, dict] = {
    1: {"id": 1, "name": "Wireless Mouse", "category": "Electronics", "price": 29.99, "stock": 100},
    2: {"id": 2, "name": "Mechanical Keyboard", "category": "Electronics", "price": 49.99, "stock": 50},
    3: {"id": 3, "name": "Python Crash Course", "category": "Books", "price": 19.99, "stock": 200},
}


def _next_product_id() -> int:
    return (max(PRODUCTS) + 1) if PRODUCTS else 1


# ============================================================
# Router Definition
# ------------------------------------------------------------
# Attaching require_api_key as a router-level dependency makes
# EVERY product endpoint show the lock icon + Authorize support.
# The shared 401 response is documented once here.
# ============================================================

product_router = APIRouter(
    prefix="/products",
    tags=["Products"],
    dependencies=[Depends(require_api_key)],
    responses={
        status.HTTP_401_UNAUTHORIZED: {
            "model": ErrorResponse,
            "description": "Missing or invalid `X-API-Key` header.",
        }
    },
)

# ============================================================
# Health / Root Endpoints
# ============================================================


@app.get(
    "/",
    tags=["Health"],
    summary="API welcome message",
    response_description="A short welcome payload.",
)
def home():
    """Public root endpoint. **No API key required.**"""
    return {"message": "Welcome to ShopSmart API"}


@app.get(
    "/health",
    tags=["Health"],
    summary="Health check",
    response_description="Service status, suitable for load-balancer probes.",
    responses={
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
    "",
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
    response_model=List[ProductOut],
    summary="List all products",
    response_description="The full product catalog.",
    responses={
        200: {
            "description": "List of all products in the catalog.",
            "headers": TIMING_HEADERS,
        }
    },
)
def list_products():
    """Return **every** product in the catalog.

    In a real service this would be paginated. Here it returns the
    full in-memory catalog so you can see the response shape.
    """
    print("Executing list_products endpoint")
    return list(PRODUCTS.values())


@product_router.get(
    "/{product_id}",
    response_model=ProductOut,
    summary="Get a single product",
    response_description="The requested product.",
    responses={
        200: {"description": "Product found.", "headers": TIMING_HEADERS},
        404: {
            "model": ErrorResponse,
            "description": "No product exists with the given ID.",
        },
    },
)
def get_product(
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

    product = PRODUCTS.get(product_id)
    if product is None:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"detail": f"Product {product_id} not found"},
        )
    return product


@product_router.post(
    "/insert",
    response_model=ProductOut,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new product",
    response_description="The newly created product, including its server-assigned ID.",
    responses={
        201: {"description": "Product created successfully.", "headers": TIMING_HEADERS},
        422: {
            "description": "Validation error — one or more fields are invalid.",
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
def create_product(product: ProductIn):
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

    product_data = product.model_dump()
    new_id = _next_product_id()

    created_product = {
        "id": new_id,
        "name": product_data["name"],
        # category is an Enum -> store its string value
        "category": product_data["category"].value
        if isinstance(product_data["category"], ProductCategory)
        else product_data["category"],
        "price": product_data["price"],
        "stock": product_data["stock"],
    }

    PRODUCTS[new_id] = created_product
    return created_product


# ============================================================
# Register Routers
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
# Example request:
#   curl -X GET http://localhost:8000/products/list \
#        -H "X-API-Key: demo-key-123"
# ============================================================