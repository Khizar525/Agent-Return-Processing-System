"""
Shared pytest fixtures for all Agent 01 test modules.
Owner: Project Lead

Loads the 5 JSON fixture files and provides lookup helpers.
Used by:
    - test_integration.py          (Lead)
    - test_policy_agent.py         (Member 2)
    - test_tools.py                (Member 3)
    - test_comm_escalation.py      (Member 4)

Usage:
    def test_something(orders, customers, get_order):
        order = get_order("ord_1002")
        customer = get_customer("cust_001")
"""

import json
import os
from collections.abc import Callable

import pytest

_FIXTURE_DIR = os.path.join(os.path.dirname(__file__), "fixtures")


# ---------------------------------------------------------------------------
# Configure openai-agents MultiProvider for OpenRouter model names
# (e.g. "meta-llama/llama-3.3-70b-instruct:free") — without this the
# SDK interprets the "/" as a provider prefix and rejects the model name.
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True, scope="session")
def _configure_model_provider():
    import agents.models.multi_provider as _mp

    _orig_init = _mp.MultiProvider.__init__

    def _patched_init(self, *args, **kwargs):  # type: ignore[no-untyped-def]
        kwargs.setdefault("unknown_prefix_mode", "model_id")
        _orig_init(self, *args, **kwargs)

    _mp.MultiProvider.__init__ = _patched_init  # type: ignore[method-assign]


# ---------------------------------------------------------------------------
# Full-list fixtures  (session-scoped — loaded once per test run)
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def orders() -> list[dict]:
    with open(os.path.join(_FIXTURE_DIR, "orders.json")) as f:
        return json.load(f)


@pytest.fixture(scope="session")
def customers() -> list[dict]:
    with open(os.path.join(_FIXTURE_DIR, "customers.json")) as f:
        return json.load(f)


@pytest.fixture(scope="session")
def fraud_signals() -> list[dict]:
    with open(os.path.join(_FIXTURE_DIR, "fraud_signals.json")) as f:
        return json.load(f)


@pytest.fixture(scope="session")
def messages() -> list[dict]:
    with open(os.path.join(_FIXTURE_DIR, "messages.json")) as f:
        return json.load(f)


@pytest.fixture(scope="session")
def resolutions() -> list[dict]:
    with open(os.path.join(_FIXTURE_DIR, "resolutions.json")) as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# Single-record lookup helpers
# These return a callable that fetches an item by its ID field.
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def get_customer(customers: list[dict]) -> Callable[[str], dict | None]:
    def _lookup(customer_id: str) -> dict | None:
        return next((c for c in customers if c["customer_id"] == customer_id), None)

    return _lookup


@pytest.fixture(scope="session")
def get_order(orders: list[dict]) -> Callable[[str], dict | None]:
    def _lookup(order_id: str) -> dict | None:
        return next((o for o in orders if o["order_id"] == order_id), None)

    return _lookup


@pytest.fixture(scope="session")
def get_fraud_signal(fraud_signals: list[dict]) -> Callable[[str], dict | None]:
    def _lookup(signal_id: str) -> dict | None:
        return next((s for s in fraud_signals if s["signal_id"] == signal_id), None)

    return _lookup


@pytest.fixture(scope="session")
def get_message(messages: list[dict]) -> Callable[[str], dict | None]:
    def _lookup(message_id: str) -> dict | None:
        return next((m for m in messages if m["message_id"] == message_id), None)

    return _lookup


@pytest.fixture(scope="session")
def get_resolution(resolutions: list[dict]) -> Callable[[str], dict | None]:
    def _lookup(resolution_id: str) -> dict | None:
        return next((r for r in resolutions if r["resolution_id"] == resolution_id), None)

    return _lookup
