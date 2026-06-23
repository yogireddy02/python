"""
contracts.py  —  THE CONTRACT between client and server.

A 'contract' is the agreed shape of data: what the client must SEND and what the
server promises to RETURN. We write it once with Pydantic models. FastAPI then:
  - validates incoming requests against it (bad data -> automatic 422),
  - documents it in Swagger automatically,
  - guarantees responses match the declared shape.

If the client and server both honour the contract, neither needs to know the
other's internals — that is exactly the REST 'client/server' idea from Day 09.
"""
from pydantic import BaseModel, Field
from typing import Optional


# ----- what the client SENDS to create a product (the request contract) -----
class ProductIn(BaseModel):
    name: str = Field(min_length=1, examples=["Wireless Mouse"])
    category: str = Field(min_length=1, examples=["Electronics"])
    price: float = Field(gt=0, examples=[29.99])          # must be > 0
    stock: int = Field(ge=0, default=0, examples=[120])    # must be >= 0


# ----- what the client sends to UPDATE (every field optional) -----
class ProductUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1)
    category: Optional[str] = Field(default=None, min_length=1)
    price: Optional[float] = Field(default=None, gt=0)
    stock: Optional[int] = Field(default=None, ge=0)


# ----- what the server RETURNS for a product (the response contract) -----
class ProductOut(BaseModel):
    id: int
    name: str
    category: str
    price: float
    stock: int


# ----- reviews (a nested resource under a product) -----
class ReviewIn(BaseModel):
    rating: int = Field(ge=1, le=5, examples=[5])          # 1..5 only
    title: str = Field(min_length=1, examples=["Great value"])


class ReviewOut(BaseModel):
    product_id: int
    rating: int
    title: str
