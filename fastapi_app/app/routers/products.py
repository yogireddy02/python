"""
routers/products.py  —  the Product resource (client -> response, DB update).

A ROUTER groups related endpoints. Each function below handles one
verb + path. FastAPI reads the type hints and the contract models to:
  - parse and validate the request,
  - call our database functions,
  - return a response that matches the contract.

Mapping (REST verbs from Day 09):
  GET    /products          -> list      (read many)
  GET    /products/{id}     -> get one   (read one)
  POST   /products          -> create    (DB insert)   -> 201
  PUT    /products/{id}     -> update     (DB update)
  DELETE /products/{id}     -> remove     (DB delete)
"""
from fastapi import APIRouter, HTTPException, status, Header
from .. import database as db
from ..contracts import ProductIn, ProductUpdate, ProductOut

# tags=["Products"] groups these under one heading in Swagger
router = APIRouter(prefix="/products", tags=["Products"])


@router.get("", response_model=list[ProductOut])
def list_products(category: str | None = None,x_api_key: str = Header(...)):
    """List products. Optional ?category= filter (a query parameter)."""
    return db.list_products(category)

@router.post("", response_model=ProductOut, status_code=status.HTTP_201_CREATED)
def create_product(product: ProductIn,x_api_key: str = Header(...)):
    """
    Create a product. The body is validated against ProductIn (the contract):
    a missing field or price <= 0 is rejected automatically with 422.
    Returns 201 Created with the new product (now carrying an id).
    """
    return db.insert_product(product.model_dump())



@router.get("/{product_id}", response_model=ProductOut)
def get_product(product_id: int,x_api_key: str = Header(...)):
    """Get ONE product by id (a path parameter)."""
    row = db.get_product(product_id)
    if row is None:
        # the resource doesn't exist -> 404 (your fault: asked for a missing id)
        raise HTTPException(status_code=404, detail=f"Product {product_id} not found")
    return row


@router.put("/{product_id}", response_model=ProductOut)
def update_product(product_id: int, changes: ProductUpdate,x_api_key: str = Header(...)):
    """Update an existing product. Only the fields sent are changed."""
    row = db.update_product(product_id, changes.model_dump())
    if row is None:
        raise HTTPException(status_code=404, detail=f"Product {product_id} not found")
    return row


@router.delete("/{product_id}")
def delete_product(product_id: int, x_api_key: str = Header(...)):
    """Delete a product. Returns a small status body."""
    if not db.delete_product(product_id):
        raise HTTPException(status_code=404, detail=f"Product {product_id} not found")
    return {"status": "deleted", "id": product_id}
