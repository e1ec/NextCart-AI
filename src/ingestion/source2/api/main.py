from fastapi import Depends, FastAPI, HTTPException, Query
from mangum import Mangum
from sqlalchemy.orm import Session

from database import get_db
from models import Aisle, Department, Product
from schemas import AisleOut, DepartmentOut, PaginatedProducts, ProductDetailOut, ProductOut

app = FastAPI(title="NextCart Product API", version="1.0.0")


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/departments", response_model=list[DepartmentOut])
def list_departments(db: Session = Depends(get_db)):
    return db.query(Department).order_by(Department.department_id).all()


@app.get("/aisles", response_model=list[AisleOut])
def list_aisles(db: Session = Depends(get_db)):
    return db.query(Aisle).order_by(Aisle.aisle_id).all()


@app.get("/products", response_model=PaginatedProducts)
def list_products(
    page: int = Query(1, ge=1),
    page_size: int = Query(500, ge=1, le=1000),
    department_id: int | None = None,
    aisle_id: int | None = None,
    db: Session = Depends(get_db),
):
    q = db.query(Product)
    if department_id is not None:
        q = q.filter(Product.department_id == department_id)
    if aisle_id is not None:
        q = q.filter(Product.aisle_id == aisle_id)
    total = q.count()
    items = q.offset((page - 1) * page_size).limit(page_size).all()
    return PaginatedProducts(total=total, page=page, page_size=page_size, items=items)


@app.get("/products/{product_id}", response_model=ProductDetailOut)
def get_product(product_id: int, db: Session = Depends(get_db)):
    product = db.query(Product).filter(Product.product_id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return ProductDetailOut(
        **ProductOut.model_validate(product).model_dump(),
        aisle=product.aisle_rel.aisle,
        department=product.department_rel.department,
    )


# AWS Lambda entry point (Mangum adapter)
handler = Mangum(app, lifespan="off")
