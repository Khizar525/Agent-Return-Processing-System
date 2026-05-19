# tests/fixtures/

This directory contains test data fixtures used by unit and integration tests.

## Files to add (Lead will populate before Phase 1 ends)

| File | Purpose | Used By |
|------|---------|---------|
| `customers.json` | Mock customer profiles (incl. fraud-flagged accounts) | M2, M3 tests |
| `orders.json` | Mock order data (in-window, out-of-window, excluded items) | M2, M3 tests |
| `fraud_signals.json` | Known fraud patterns for Policy Agent cross-reference test | M2 tests |
| `messages.json` | Sample inbound messages for all intent types | Integration tests |
| `resolutions.json` | Expected resolution outputs for integration assertions | Integration tests |

Do not commit real customer data here. All fixtures must be synthetic.
