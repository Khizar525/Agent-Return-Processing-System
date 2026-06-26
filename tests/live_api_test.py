"""
Live API integration test — fires all 5 demo scenarios at the running server.
Run AFTER: uvicorn main:app --reload --port 8000

Usage (standalone):
    python tests/live_api_test.py

NOTE: This is NOT a pytest test file. It runs outside of pytest.
Top-level code is guarded under ``if __name__ == "__main__"`` to avoid
breaking pytest collection.
"""

import json
import sys
import time
import urllib.request
import urllib.error

BASE = "http://127.0.0.1:8000"

SCENARIOS = [
    (
        "Alice  — eligible refund",
        "CUST-001",
        "I want to return my order ORD-001, please process a refund.",
    ),
    (
        "Bob    — excluded digital goods",
        "CUST-002",
        "I want to return my digital download order ORD-003.",
    ),
    (
        "Charlie— damaged replacement",
        "CUST-003",
        "My item from order ORD-004 arrived damaged, I need a replacement.",
    ),
    ("Dave   — fraud flag reject", "CUST-004", "Return order ORD-005 please."),
    ("Eve    — fraud DB escalate", "CUST-005", "I need to return order ORD-006."),
]


def main() -> None:
    """Run all demo scenarios against the live server."""
    # ── health check ──────────────────────────────────────────────────────────
    print("=" * 70)
    print("  Agent 01 — Live API Integration Test")
    print("=" * 70)

    try:
        with urllib.request.urlopen(f"{BASE}/health", timeout=5) as r:
            health = json.loads(r.read())
            print(f"  Server health : {health}")
    except Exception as exc:
        print(f"  ERROR: Server not reachable — {exc}")
        sys.exit(1)

    print()

    # ── scenario runs ─────────────────────────────────────────────────────────
    passed = 0
    failed = 0

    for label, cust_id, message in SCENARIOS:
        payload = json.dumps(
            {"customer_id": cust_id, "channel": "web_chat", "raw_message": message}
        ).encode()

        req = urllib.request.Request(
            f"{BASE}/webhook/message",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read())
                sid = data.get("session_id", "n/a")
                chain = data.get("agent_chain", [])
                resolution = data.get("resolution", "")
                print(f"[PASS] {label}")
                print(f"       customer    : {cust_id}")
                print(f"       session_id  : {sid}")
                print(f"       agent_chain : {chain}")
                print(f"       resolution  : {resolution[:300]}")
                passed += 1
        except urllib.error.HTTPError as exc:
            body = exc.read().decode(errors="replace")
            print(f"[FAIL] {label}")
            print(f"       HTTP {exc.code}: {body[:200]}")
            failed += 1
        except Exception as exc:
            print(f"[FAIL] {label}")
            print(f"       {type(exc).__name__}: {exc}")
            failed += 1

        print()
        time.sleep(1)  # small gap between calls

    # ── summary ───────────────────────────────────────────────────────────────
    print("=" * 70)
    print(f"  Results: {passed} passed  |  {failed} failed  |  {len(SCENARIOS)} total")
    print("=" * 70)
    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    main()
