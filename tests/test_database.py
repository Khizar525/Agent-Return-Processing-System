"""
Database Repository Tests — M2 Gap Fix
Owner: Project Lead

Tests all three repository backends (Memory, File, Postgres abstraction)
and the DTO dataclasses. Covers CRUD operations, edge cases, and factory.

Run:
    pytest tests/test_database.py -v
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from database.repository import (
    CustomerDTO,
    FileBackend,
    FraudDbMatchDTO,
    MemoryBackend,
    OrderDTO,
    Repository,
    create_repository,
)
from database.config import USE_FILE_BACKEND


# ── DTO Tests ────────────────────────────────────────────────────────────────


class TestOrderDTO:
    def test_construction(self) -> None:
        o = OrderDTO(
            order_id="ORD-001",
            customer_id="CUST-001",
            item_category="electronics",
            days_since_purchase=15,
            price=199.99,
            damaged=False,
        )
        assert o.order_id == "ORD-001"
        assert o.customer_id == "CUST-001"
        assert o.item_category == "electronics"
        assert o.days_since_purchase == 15
        assert o.price == 199.99
        assert o.damaged is False

    def test_damaged_order(self) -> None:
        o = OrderDTO("ORD-002", "CUST-001", "clothing", 10, 89.99, True)
        assert o.damaged is True

    def test_zero_days(self) -> None:
        o = OrderDTO("ORD-003", "CUST-001", "electronics", 0, 0.0, False)
        assert o.days_since_purchase == 0

    def test_negative_price(self) -> None:
        o = OrderDTO("ORD-004", "CUST-001", "electronics", 5, -10.0, False)
        assert o.price == -10.0


class TestCustomerDTO:
    def test_construction_no_fraud(self) -> None:
        c = CustomerDTO(customer_id="CUST-001", fraud_flag=False, fraud_reason=None)
        assert c.customer_id == "CUST-001"
        assert c.fraud_flag is False
        assert c.fraud_reason is None

    def test_construction_with_fraud(self) -> None:
        c = CustomerDTO(customer_id="CUST-004", fraud_flag=True, fraud_reason="chargeback_history")
        assert c.fraud_flag is True
        assert c.fraud_reason == "chargeback_history"


class TestFraudDbMatchDTO:
    def test_construction(self) -> None:
        f = FraudDbMatchDTO(customer_id="CUST-005", match_reason="suspicious_pattern_alpha")
        assert f.customer_id == "CUST-005"
        assert f.match_reason == "suspicious_pattern_alpha"


# ── MemoryBackend Tests ──────────────────────────────────────────────────────


class TestMemoryBackend:
    @pytest.fixture
    def repo(self) -> MemoryBackend:
        return MemoryBackend()

    # -- get_order --

    @pytest.mark.asyncio
    async def test_get_order_exists(self, repo: MemoryBackend) -> None:
        order = await repo.get_order("ORD-001")
        assert order is not None
        assert order.order_id == "ORD-001"
        assert order.customer_id == "CUST-001"
        assert order.item_category == "electronics"

    @pytest.mark.asyncio
    async def test_get_order_not_found(self, repo: MemoryBackend) -> None:
        order = await repo.get_order("ORD-999")
        assert order is None

    @pytest.mark.asyncio
    async def test_get_order_empty_string(self, repo: MemoryBackend) -> None:
        order = await repo.get_order("")
        assert order is None

    @pytest.mark.asyncio
    async def test_get_order_all_default_records(self, repo: MemoryBackend) -> None:
        """Verify all 15 default orders are loadable."""
        for i in range(1, 16):
            order = await repo.get_order(f"ORD-{i:03d}")
            assert order is not None, f"ORD-{i:03d} not found"

    # -- get_customer --

    @pytest.mark.asyncio
    async def test_get_customer_exists(self, repo: MemoryBackend) -> None:
        customer = await repo.get_customer("CUST-001")
        assert customer is not None
        assert customer.customer_id == "CUST-001"
        assert customer.fraud_flag is False

    @pytest.mark.asyncio
    async def test_get_customer_fraud_flag(self, repo: MemoryBackend) -> None:
        customer = await repo.get_customer("CUST-004")
        assert customer is not None
        assert customer.fraud_flag is True
        assert customer.fraud_reason == "chargeback_history"

    @pytest.mark.asyncio
    async def test_get_customer_not_found(self, repo: MemoryBackend) -> None:
        customer = await repo.get_customer("CUST-999")
        assert customer is None

    @pytest.mark.asyncio
    async def test_get_customer_empty_string(self, repo: MemoryBackend) -> None:
        customer = await repo.get_customer("")
        assert customer is None

    # -- get_fraud_db_match --

    @pytest.mark.asyncio
    async def test_get_fraud_db_match_exists(self, repo: MemoryBackend) -> None:
        match = await repo.get_fraud_db_match("CUST-005")
        assert match is not None
        assert match.customer_id == "CUST-005"
        assert match.match_reason == "suspicious_pattern_alpha"

    @pytest.mark.asyncio
    async def test_get_fraud_db_match_not_found(self, repo: MemoryBackend) -> None:
        match = await repo.get_fraud_db_match("CUST-999")
        assert match is None

    @pytest.mark.asyncio
    async def test_get_fraud_db_match_no_flag_customer(self, repo: MemoryBackend) -> None:
        """CUST-001 has no fraud DB match."""
        match = await repo.get_fraud_db_match("CUST-001")
        assert match is None

    # -- set_order / set_customer --

    def test_set_order_updates_field(self, repo: MemoryBackend) -> None:
        repo.set_order("ORD-001", damaged=True)
        assert repo.orders["ORD-001"]["damaged"] is True

    def test_set_order_nonexistent(self, repo: MemoryBackend) -> None:
        """Setting a nonexistent order should not crash."""
        repo.set_order("ORD-999", damaged=True)

    def test_set_customer_updates_field(self, repo: MemoryBackend) -> None:
        repo.set_customer("CUST-001", fraud_flag=True)
        assert repo.customers["CUST-001"]["fraud_flag"] is True

    def test_set_customer_nonexistent(self, repo: MemoryBackend) -> None:
        """Setting a nonexistent customer should not crash."""
        repo.set_customer("CUST-999", fraud_flag=True)

    # -- close --

    @pytest.mark.asyncio
    async def test_close(self, repo: MemoryBackend) -> None:
        await repo.close()  # should not raise

    # -- custom data --

    @pytest.mark.asyncio
    async def test_custom_data(self) -> None:
        data = {
            "orders": {
                "O-1": {
                    "order_id": "O-1",
                    "customer_id": "C-1",
                    "item_category": "x",
                    "days_since_purchase": 1,
                    "price": 10.0,
                    "damaged": False,
                }
            },
            "customers": {"C-1": {"customer_id": "C-1", "fraud_flag": False, "fraud_reason": None}},
            "fraud_db_matches": {},
        }
        repo = MemoryBackend(data)
        order = await repo.get_order("O-1")
        assert order is not None
        assert order.price == 10.0

    @pytest.mark.asyncio
    async def test_empty_data(self) -> None:
        repo = MemoryBackend({})
        assert await repo.get_order("ORD-001") is None
        assert await repo.get_customer("CUST-001") is None
        assert await repo.get_fraud_db_match("CUST-005") is None

    @pytest.mark.asyncio
    async def test_none_data_uses_default(self) -> None:
        repo = MemoryBackend(None)
        order = await repo.get_order("ORD-001")
        assert order is not None


# ── FileBackend Tests ────────────────────────────────────────────────────────


class TestFileBackend:
    @pytest.fixture
    def tmp_file(self, tmp_path: Path) -> str:
        return str(tmp_path / "test_db.json")

    @pytest.mark.asyncio
    async def test_loads_from_file(self, tmp_file: str) -> None:
        data = {
            "orders": {
                "O-1": {
                    "order_id": "O-1",
                    "customer_id": "C-1",
                    "item_category": "electronics",
                    "days_since_purchase": 5,
                    "price": 99.99,
                    "damaged": False,
                }
            },
            "customers": {"C-1": {"customer_id": "C-1", "fraud_flag": False, "fraud_reason": None}},
            "fraud_db_matches": {},
        }
        with open(tmp_file, "w") as f:
            json.dump(data, f)

        repo = FileBackend(tmp_file)
        order = await repo.get_order("O-1")
        assert order is not None
        assert order.price == 99.99

    @pytest.mark.asyncio
    async def test_creates_default_if_missing(self, tmp_file: str) -> None:
        repo = FileBackend(tmp_file)
        order = await repo.get_order("ORD-001")
        assert order is not None
        assert os.path.exists(tmp_file)

    @pytest.mark.asyncio
    async def test_get_order_not_found(self, tmp_file: str) -> None:
        repo = FileBackend(tmp_file)
        order = await repo.get_order("ORD-999")
        assert order is None

    @pytest.mark.asyncio
    async def test_get_customer(self, tmp_file: str) -> None:
        repo = FileBackend(tmp_file)
        customer = await repo.get_customer("CUST-001")
        assert customer is not None
        assert customer.customer_id == "CUST-001"

    @pytest.mark.asyncio
    async def test_get_customer_not_found(self, tmp_file: str) -> None:
        repo = FileBackend(tmp_file)
        customer = await repo.get_customer("CUST-999")
        assert customer is None

    @pytest.mark.asyncio
    async def test_get_fraud_db_match(self, tmp_file: str) -> None:
        repo = FileBackend(tmp_file)
        match = await repo.get_fraud_db_match("CUST-005")
        assert match is not None
        assert match.match_reason == "suspicious_pattern_alpha"

    @pytest.mark.asyncio
    async def test_get_fraud_db_match_not_found(self, tmp_file: str) -> None:
        repo = FileBackend(tmp_file)
        match = await repo.get_fraud_db_match("CUST-999")
        assert match is None

    @pytest.mark.asyncio
    async def test_close_resets_cache(self, tmp_file: str) -> None:
        repo = FileBackend(tmp_file)
        await repo.get_order("ORD-001")  # loads data
        await repo.close()
        assert repo._data is None

    @pytest.mark.asyncio
    async def test_caches_data(self, tmp_file: str) -> None:
        repo = FileBackend(tmp_file)
        await repo.get_order("ORD-001")
        assert repo._data is not None
        # Second call should use cache
        order = await repo.get_order("ORD-002")
        assert order is not None


# ── Factory Tests ────────────────────────────────────────────────────────────


class TestFactory:
    def test_create_repository_returns_repository(self) -> None:
        repo = create_repository()
        assert isinstance(repo, Repository)

    def test_file_backend_default(self) -> None:
        """When USE_FILE_BACKEND=1, factory returns FileBackend."""
        repo = create_repository()
        if USE_FILE_BACKEND:
            assert isinstance(repo, FileBackend)
        else:
            # PostgresBackend in prod — just verify it's a Repository
            assert isinstance(repo, Repository)
