"""
Repository — data access abstraction
Owner: Member 2

Two implementations:
  - PostgresBackend  (production — SQLAlchemy + asyncpg)
  - FileBackend      (dev — JSON file, same interface)

Auto-selected via USE_FILE_BACKEND env var.
"""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from contextlib import asynccontextmanager
from collections.abc import AsyncIterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from database.config import FILE_DB_PATH, USE_FILE_BACKEND


# ── Data transfer objects ────────────────────────────────────────────────────


@dataclass
class OrderDTO:
    order_id: str
    customer_id: str
    item_category: str
    days_since_purchase: int
    price: float
    damaged: bool


@dataclass
class CustomerDTO:
    customer_id: str
    fraud_flag: bool
    fraud_reason: str | None


@dataclass
class FraudDbMatchDTO:
    customer_id: str
    match_reason: str


# ── Abstract repository ──────────────────────────────────────────────────────


class Repository(ABC):
    @abstractmethod
    async def get_order(self, order_id: str) -> OrderDTO | None:
        ...

    @abstractmethod
    async def get_customer(self, customer_id: str) -> CustomerDTO | None:
        ...

    @abstractmethod
    async def get_fraud_db_match(self, customer_id: str) -> FraudDbMatchDTO | None:
        ...

    @abstractmethod
    async def close(self) -> None:
        ...


# ── PostgreSQL backend (production) ──────────────────────────────────────────


class PostgresBackend(Repository):
    """Production backend — uses SQLAlchemy async with asyncpg."""

    def __init__(self) -> None:
        self._engine: Any = None
        self._session_factory: Any = None

    async def _ensure_engine(self) -> Any:
        if self._engine is not None:
            return self._engine
        from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
        from database.config import DATABASE_URL, DB_ECHO

        self._engine = create_async_engine(DATABASE_URL, echo=DB_ECHO)
        self._session_factory = async_sessionmaker(self._engine, expire_on_commit=False)
        return self._engine

    @asynccontextmanager
    async def _session(self) -> AsyncIterator[Any]:
        await self._ensure_engine()
        async with self._session_factory() as session:
            yield session

    async def get_order(self, order_id: str) -> OrderDTO | None:
        from database.models import OrderModel
        from sqlalchemy import select

        async with self._session() as session:
            row = (await session.execute(select(OrderModel).where(OrderModel.order_id == order_id))).scalar_one_or_none()
            if row is None:
                return None
            return OrderDTO(
                order_id=row.order_id,
                customer_id=row.customer_id,
                item_category=row.item_category,
                days_since_purchase=row.days_since_purchase,
                price=float(row.price),
                damaged=row.damaged,
            )

    async def get_customer(self, customer_id: str) -> CustomerDTO | None:
        from database.models import CustomerModel
        from sqlalchemy import select

        async with self._session() as session:
            row = (await session.execute(select(CustomerModel).where(CustomerModel.customer_id == customer_id))).scalar_one_or_none()
            if row is None:
                return None
            return CustomerDTO(
                customer_id=row.customer_id,
                fraud_flag=row.fraud_flag,
                fraud_reason=row.fraud_reason,
            )

    async def get_fraud_db_match(self, customer_id: str) -> FraudDbMatchDTO | None:
        from database.models import FraudDbMatchModel
        from sqlalchemy import select

        async with self._session() as session:
            row = (await session.execute(select(FraudDbMatchModel).where(FraudDbMatchModel.customer_id == customer_id))).scalar_one_or_none()
            if row is None:
                return None
            return FraudDbMatchDTO(
                customer_id=row.customer_id,
                match_reason=row.match_reason,
            )

    async def close(self) -> None:
        if self._engine:
            await self._engine.dispose()


# ── File-based backend (development) ─────────────────────────────────────────


_DEFAULT_DATA: dict[str, Any] = {
    "orders": {
        # ── Existing test records (do not modify) ────────────────────────
        "ORD-001": {"order_id": "ORD-001", "customer_id": "CUST-001", "item_category": "electronics", "days_since_purchase": 15, "price": 199.99, "damaged": False},
        "ORD-002": {"order_id": "ORD-002", "customer_id": "CUST-001", "item_category": "electronics", "days_since_purchase": 45, "price": 299.99, "damaged": False},
        "ORD-003": {"order_id": "ORD-003", "customer_id": "CUST-002", "item_category": "digital_goods", "days_since_purchase": 5, "price": 49.99, "damaged": False},
        "ORD-004": {"order_id": "ORD-004", "customer_id": "CUST-003", "item_category": "clothing", "days_since_purchase": 10, "price": 89.99, "damaged": True},
        "ORD-005": {"order_id": "ORD-005", "customer_id": "CUST-004", "item_category": "home_goods", "days_since_purchase": 20, "price": 150.00, "damaged": False},
        "ORD-006": {"order_id": "ORD-006", "customer_id": "CUST-005", "item_category": "electronics", "days_since_purchase": 3, "price": 799.99, "damaged": False},
        # ── Extra demo records ──────────────────────────────────────────
        "ORD-007": {"order_id": "ORD-007", "customer_id": "CUST-001", "item_category": "perishables",     "days_since_purchase": 2,  "price": 12.99,  "damaged": False},
        "ORD-008": {"order_id": "ORD-008", "customer_id": "CUST-003", "item_category": "electronics",     "days_since_purchase": 0,  "price": 549.00, "damaged": False},
        "ORD-009": {"order_id": "ORD-009", "customer_id": "CUST-003", "item_category": "electronics",     "days_since_purchase": 30, "price": 29.99,  "damaged": False},
        "ORD-010": {"order_id": "ORD-010", "customer_id": "CUST-006", "item_category": "home_goods",      "days_since_purchase": 12, "price": 89.99,  "damaged": False},
        "ORD-011": {"order_id": "ORD-011", "customer_id": "CUST-002", "item_category": "electronics",     "days_since_purchase": 8,  "price": 45.00,  "damaged": False},
        "ORD-012": {"order_id": "ORD-012", "customer_id": "CUST-001", "item_category": "beauty",          "days_since_purchase": 25, "price": 34.99,  "damaged": True},
        "ORD-013": {"order_id": "ORD-013", "customer_id": "CUST-007", "item_category": "electronics",     "days_since_purchase": 5,  "price": 999.99, "damaged": False},
        "ORD-014": {"order_id": "ORD-014", "customer_id": "CUST-006", "item_category": "final_sale",      "days_since_purchase": 1,  "price": 199.00, "damaged": False},
        "ORD-015": {"order_id": "ORD-015", "customer_id": "CUST-008", "item_category": "electronics",     "days_since_purchase": 7,  "price": 250.00, "damaged": False},
    },
    "customers": {
        # ── Existing test records (do not modify) ────────────────────────
        "CUST-001": {"customer_id": "CUST-001", "fraud_flag": False, "fraud_reason": None},
        "CUST-002": {"customer_id": "CUST-002", "fraud_flag": False, "fraud_reason": None},
        "CUST-003": {"customer_id": "CUST-003", "fraud_flag": False, "fraud_reason": None},
        "CUST-004": {"customer_id": "CUST-004", "fraud_flag": True,  "fraud_reason": "chargeback_history"},
        "CUST-005": {"customer_id": "CUST-005", "fraud_flag": False, "fraud_reason": None},
        # ── Extra demo records ──────────────────────────────────────────
        "CUST-006": {"customer_id": "CUST-006", "fraud_flag": False, "fraud_reason": None},
        "CUST-007": {"customer_id": "CUST-007", "fraud_flag": True,  "fraud_reason": "multiple_chargebacks"},
        "CUST-008": {"customer_id": "CUST-008", "fraud_flag": False, "fraud_reason": None},
    },
    "fraud_db_matches": {
        # ── Existing test records ────────────────────────────────────────
        "CUST-005": {"customer_id": "CUST-005", "match_reason": "suspicious_pattern_alpha"},
        # ── Extra demo records ──────────────────────────────────────────
        "CUST-008": {"customer_id": "CUST-008", "match_reason": "flagged_by_velocity_check"},
    },
}


class FileBackend(Repository):
    """Dev backend — stores data in a JSON file. Same interface as PostgresBackend."""

    def __init__(self, path: str | None = None) -> None:
        self._path = Path(path or FILE_DB_PATH)
        self._data: dict[str, Any] | None = None

    def _load(self) -> dict[str, Any]:
        if self._data is not None:
            return self._data
        if self._path.exists():
            with open(self._path, encoding="utf-8") as f:
                self._data = json.load(f)
        else:
            self._data = _DEFAULT_DATA
            self._save()
        return self._data

    def _save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with open(self._path, "w", encoding="utf-8") as f:
            json.dump(self._data, f, indent=2, default=str)

    async def get_order(self, order_id: str) -> OrderDTO | None:
        raw = self._load()["orders"].get(order_id)
        if raw is None:
            return None
        return OrderDTO(**raw)

    async def get_customer(self, customer_id: str) -> CustomerDTO | None:
        raw = self._load()["customers"].get(customer_id)
        if raw is None:
            return None
        return CustomerDTO(**raw)

    async def get_fraud_db_match(self, customer_id: str) -> FraudDbMatchDTO | None:
        raw = self._load()["fraud_db_matches"].get(customer_id)
        if raw is None:
            return None
        return FraudDbMatchDTO(**raw)

    async def close(self) -> None:
        self._data = None


# ── In-memory backend (testing) ─────────────────────────────────────────────


class MemoryBackend(Repository):
    """In-memory backend — stores data in a plain dict. Used by tests."""

    def __init__(self, data: dict[str, Any] | None = None) -> None:
        import copy
        self._data = copy.deepcopy(data) if data is not None else copy.deepcopy(_DEFAULT_DATA)

    @property
    def orders(self) -> dict[str, dict[str, Any]]:
        return cast("dict[str, dict[str, Any]]", self._data.setdefault("orders", {}))

    @property
    def customers(self) -> dict[str, dict[str, Any]]:
        return cast("dict[str, dict[str, Any]]", self._data.setdefault("customers", {}))

    @property
    def fraud_db_matches(self) -> dict[str, dict[str, Any]]:
        return cast("dict[str, dict[str, Any]]", self._data.setdefault("fraud_db_matches", {}))

    async def get_order(self, order_id: str) -> OrderDTO | None:
        raw = self.orders.get(order_id)
        if raw is None:
            return None
        return OrderDTO(**raw)

    async def get_customer(self, customer_id: str) -> CustomerDTO | None:
        raw = self.customers.get(customer_id)
        if raw is None:
            return None
        return CustomerDTO(**raw)

    async def get_fraud_db_match(self, customer_id: str) -> FraudDbMatchDTO | None:
        raw = self.fraud_db_matches.get(customer_id)
        if raw is None:
            return None
        return FraudDbMatchDTO(**raw)

    def set_order(self, order_id: str, **kwargs: Any) -> None:
        """Update an order's fields in-place (for tests)."""
        if order_id in self.orders:
            self.orders[order_id].update(kwargs)

    def set_customer(self, customer_id: str, **kwargs: Any) -> None:
        """Update a customer's fields in-place (for tests)."""
        if customer_id in self.customers:
            self.customers[customer_id].update(kwargs)

    async def close(self) -> None:
        pass


# ── Factory ──────────────────────────────────────────────────────────────────


def create_repository() -> Repository:
    if USE_FILE_BACKEND:
        return FileBackend()
    return PostgresBackend()
