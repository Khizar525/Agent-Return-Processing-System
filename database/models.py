"""
SQLAlchemy ORM models — mirrors PostgreSQL schema
Owner: Member 2

Target: PostgreSQL via asyncpg. Uses SQLAlchemy 2.0 style.
"""

from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

from sqlalchemy import Boolean, DateTime, DECIMAL, Index, Integer, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class CustomerModel(Base):
    __tablename__ = "customers"

    customer_id: Mapped[str] = mapped_column(String(20), primary_key=True)
    fraud_flag: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    fraud_reason: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )

    orders: Mapped[list["OrderModel"]] = relationship(back_populates="customer")
    fraud_db_match: Mapped[Optional["FraudDbMatchModel"]] = relationship(back_populates="customer", uselist=False)


class OrderModel(Base):
    __tablename__ = "orders"

    order_id: Mapped[str] = mapped_column(String(20), primary_key=True)
    customer_id: Mapped[str] = mapped_column(String(20), nullable=False)
    item_category: Mapped[str] = mapped_column(String(50), nullable=False)
    days_since_purchase: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    price: Mapped[Decimal] = mapped_column(DECIMAL(10, 2), default=0, nullable=False)
    damaged: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )

    customer: Mapped["CustomerModel"] = relationship(back_populates="orders")

    __table_args__ = (
        Index("idx_orders_customer", "customer_id"),
    )


class FraudDbMatchModel(Base):
    __tablename__ = "fraud_db_matches"

    customer_id: Mapped[str] = mapped_column(String(20), primary_key=True)
    match_reason: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )

    customer: Mapped["CustomerModel"] = relationship(back_populates="fraud_db_match")
