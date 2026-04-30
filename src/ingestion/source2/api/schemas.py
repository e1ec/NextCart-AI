from pydantic import BaseModel


class DepartmentOut(BaseModel):
    department_id: int
    department: str
    model_config = {"from_attributes": True}


class AisleOut(BaseModel):
    aisle_id: int
    aisle: str
    model_config = {"from_attributes": True}


class ProductOut(BaseModel):
    product_id: int
    product_name: str
    aisle_id: int
    department_id: int
    model_config = {"from_attributes": True}


class ProductDetailOut(ProductOut):
    aisle: str
    department: str


class PaginatedProducts(BaseModel):
    total: int
    page: int
    page_size: int
    items: list[ProductOut]
