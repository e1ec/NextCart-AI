from sqlalchemy import Column, ForeignKey, Integer, SmallInteger, String
from sqlalchemy.orm import relationship

from database import Base


class Department(Base):
    __tablename__ = "departments"
    department_id = Column(SmallInteger, primary_key=True)
    department = Column(String(100), nullable=False)
    products = relationship("Product", back_populates="department_rel")


class Aisle(Base):
    __tablename__ = "aisles"
    aisle_id = Column(SmallInteger, primary_key=True)
    aisle = Column(String(200), nullable=False)
    products = relationship("Product", back_populates="aisle_rel")


class Product(Base):
    __tablename__ = "products"
    product_id = Column(Integer, primary_key=True)
    product_name = Column(String(500), nullable=False)
    aisle_id = Column(SmallInteger, ForeignKey("aisles.aisle_id"))
    department_id = Column(SmallInteger, ForeignKey("departments.department_id"))
    aisle_rel = relationship("Aisle", back_populates="products")
    department_rel = relationship("Department", back_populates="products")
