from datetime import datetime
from sqlalchemy import String, Boolean, DateTime, ForeignKey, Numeric, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column
from .db import Base

class Organization(Base):
    __tablename__="organizations"
    id: Mapped[int]=mapped_column(primary_key=True)
    name: Mapped[str]=mapped_column(String(160))
    created_at: Mapped[datetime]=mapped_column(DateTime,default=datetime.utcnow)

class User(Base):
    __tablename__="users"
    id: Mapped[int]=mapped_column(primary_key=True)
    organization_id: Mapped[int]=mapped_column(ForeignKey("organizations.id"))
    email: Mapped[str]=mapped_column(String(255),unique=True,index=True)
    password_hash: Mapped[str]=mapped_column(String(255))
    role: Mapped[str]=mapped_column(String(40),default="EMPLOYEE")
    is_active: Mapped[bool]=mapped_column(Boolean,default=True)
    created_at: Mapped[datetime]=mapped_column(DateTime,default=datetime.utcnow)

class Product(Base):
    __tablename__="products"
    id: Mapped[int]=mapped_column(primary_key=True)
    organization_id: Mapped[int]=mapped_column(ForeignKey("organizations.id"),index=True)
    name: Mapped[str]=mapped_column(String(200))
    sku: Mapped[str]=mapped_column(String(100))
    cost: Mapped[float]=mapped_column(Numeric(12,2),default=0)
    price: Mapped[float]=mapped_column(Numeric(12,2),default=0)
    reorder_level: Mapped[int]=mapped_column(Integer,default=0)

class Inventory(Base):
    __tablename__="inventory"
    id: Mapped[int]=mapped_column(primary_key=True)
    organization_id: Mapped[int]=mapped_column(ForeignKey("organizations.id"),index=True)
    product_id: Mapped[int]=mapped_column(ForeignKey("products.id"),unique=True)
    quantity: Mapped[int]=mapped_column(Integer,default=0)

class Customer(Base):
    __tablename__="customers"
    id: Mapped[int]=mapped_column(primary_key=True)
    organization_id: Mapped[int]=mapped_column(ForeignKey("organizations.id"),index=True)
    name: Mapped[str]=mapped_column(String(200))
    email: Mapped[str|None]=mapped_column(String(255),nullable=True)
    phone: Mapped[str|None]=mapped_column(String(50),nullable=True)

class Order(Base):
    __tablename__="orders"
    id: Mapped[int]=mapped_column(primary_key=True)
    organization_id: Mapped[int]=mapped_column(ForeignKey("organizations.id"),index=True)
    customer_id: Mapped[int|None]=mapped_column(ForeignKey("customers.id"),nullable=True)
    status: Mapped[str]=mapped_column(String(40),default="PENDING")
    total: Mapped[float]=mapped_column(Numeric(12,2),default=0)
    created_at: Mapped[datetime]=mapped_column(DateTime,default=datetime.utcnow)

class AuditLog(Base):
    __tablename__="audit_logs"
    id: Mapped[int]=mapped_column(primary_key=True)
    organization_id: Mapped[int]=mapped_column(ForeignKey("organizations.id"),index=True)
    actor: Mapped[str]=mapped_column(String(100))
    action: Mapped[str]=mapped_column(String(160))
    details: Mapped[str]=mapped_column(Text,default="")
    created_at: Mapped[datetime]=mapped_column(DateTime,default=datetime.utcnow)
