from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional
import uuid

app = FastAPI(title="Shop API", version="1.0.0")

# In-memory store
products: dict = {}

# ── Schemas ──────────────────────────────────────────────

class ProductCreate(BaseModel):
    name: str
    description: Optional[str] = None
    price: float
    stock: int = 0
    category: Optional[str] = None

class ProductUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    price: Optional[float] = None
    stock: Optional[int] = None
    category: Optional[str] = None

class Product(ProductCreate):
    id: str

# Seed data
for _id, _name, _desc, _price, _stock, _cat in [
    ("1", "Wireless Headphones", "Premium sound quality", 99.99, 50, "Electronics"),
    ("2", "Coffee Maker", "Brews 12 cups", 49.99, 30, "Kitchen"),
    ("3", "Running Shoes", "Lightweight and durable", 79.99, 100, "Footwear"),
]:
    products[_id] = Product(id=_id, name=_name, description=_desc, price=_price, stock=_stock, category=_cat)

# ── Routes ───────────────────────────────────────────────

@app.get("/products", response_model=list[Product], tags=["Products"])
def list_products():
    """Get all products."""
    return list(products.values())

@app.get("/products/{product_id}", response_model=Product, tags=["Products"])
def get_product(product_id: str):
    """Get a single product by ID."""
    if product_id not in products:
        raise HTTPException(status_code=404, detail="Product not found")
    return products[product_id]

@app.post("/products", response_model=Product, status_code=201, tags=["Products"])
def create_product(data: ProductCreate):
    """Create a new product."""
    product_id = str(uuid.uuid4())[:8]
    product = Product(id=product_id, **data.dict())
    products[product_id] = product
    return product

@app.put("/products/{product_id}", response_model=Product, tags=["Products"])
def update_product(product_id: str, data: ProductUpdate):
    """Update an existing product (partial update supported)."""
    if product_id not in products:
        raise HTTPException(status_code=404, detail="Product not found")
    existing = products[product_id].dict()
    updates = {k: v for k, v in data.dict().items() if v is not None}
    existing.update(updates)
    products[product_id] = Product(**existing)
    return products[product_id]

@app.delete("/products/{product_id}", tags=["Products"])
def delete_product(product_id: str):
    """Delete a product."""
    if product_id not in products:
        raise HTTPException(status_code=404, detail="Product not found")
    del products[product_id]
    return {"message": f"Product {product_id} deleted"}