"""Unit tests for Source 2 API Pydantic schemas — no DB, no AWS."""

import pytest
from pydantic import ValidationError

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../src"))

from ingestion.source2.api.schemas import (  # noqa: E402
    AisleOut,
    DepartmentOut,
    PaginatedProducts,
    ProductDetailOut,
    ProductOut,
)


def test_product_out_valid():
    p = ProductOut(product_id=1, product_name="Organic Milk", aisle_id=84, department_id=16)
    assert p.product_id == 1
    assert p.product_name == "Organic Milk"


def test_product_out_missing_field():
    with pytest.raises(ValidationError):
        ProductOut(product_id=1, aisle_id=84, department_id=16)  # missing product_name


def test_aisle_out_valid():
    a = AisleOut(aisle_id=1, aisle="prepared soups salads")
    assert a.aisle_id == 1


def test_department_out_valid():
    d = DepartmentOut(department_id=1, department="frozen")
    assert d.department_id == 1


def test_paginated_products_structure():
    items = [
        ProductOut(product_id=i, product_name=f"Product {i}", aisle_id=1, department_id=1)
        for i in range(5)
    ]
    result = PaginatedProducts(total=100, page=1, page_size=5, items=items)
    assert result.total == 100
    assert len(result.items) == 5


def test_product_detail_out():
    p = ProductDetailOut(
        product_id=1,
        product_name="Organic Milk",
        aisle_id=84,
        department_id=16,
        aisle="milk butter eggs",
        department="dairy eggs",
    )
    assert p.aisle == "milk butter eggs"
    assert p.department == "dairy eggs"
