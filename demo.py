"""
Demo -- Real customer scenarios using the Agent 01 system.
Run: python demo.py
"""

import asyncio
import json

from tools.policy_tools import RAW_CHECK_RETURN_POLICY as check_return
from guardrails.pii_scrubber import RAW_PII_SCRUBBER as scrub_pii
from guardrails.sentiment_monitor import RAW_SENTIMENT_MONITOR as score_sentiment
from guardrails.refund_cap import RAW_REFUND_CAP as check_refund_cap

DEMO_SCENARIOS: dict[str, dict[str, str]] = {
    "1": {"description": "Alice — eligible refund (ORD-001, CUST-001)"},
    "2": {"description": "Bob — excluded digital goods (ORD-003, CUST-002)"},
    "3": {"description": "Charlie — damaged item → replacement (ORD-004, CUST-003)"},
    "4": {"description": "Dave — fraud flag → escalate (ORD-005, CUST-004)"},
    "5": {"description": "Eve — fraud DB match → escalate (ORD-006, CUST-005)"},
    "6": {"description": "Too late — return window exceeded (ORD-002, CUST-001)"},
    "7": {"description": "Order not found (ORD-999, CUST-001)"},
    "8": {"description": "Customer not found (ORD-001, CUST-999)"},
    "9": {"description": "Order-customer mismatch (ORD-001, CUST-002)"},
    "10": {"description": "Excluded perishables (ORD-007, CUST-001)"},
    "11": {"description": "Same day — 0 days since purchase (ORD-008, CUST-003)"},
    "12": {"description": "Exactly 30 days — boundary (ORD-009, CUST-003)"},
    "13": {"description": "New customer — clean return (ORD-010, CUST-006)"},
    "14": {"description": "Damaged item — replacement (ORD-012, CUST-001)"},
    "15": {"description": "New fraud account — blocked (ORD-013, CUST-007)"},
    "16": {"description": "Final sale — excluded (ORD-014, CUST-006)"},
    "17": {"description": "Fraud DB match — escalate (ORD-015, CUST-008)"},
}


def p(msg):
    print(f"  {msg}")


def h(title):
    print(f"\n{'=' * 60}")
    print(f"  {title}")
    print(f"{'=' * 60}")


async def demo_policy():
    h("SCENARIO 1: Happy Path -- Return within 30 days")
    p("Customer Alice (CUST-001) bought electronics 15 days ago. Works fine, just changed mind.")
    p("> python cli.py check ORD-001 CUST-001")
    r = await check_return("ORD-001", "CUST-001")
    print(
        f"    [PASS] Eligible: {r['eligible']} | Action: {r['recommended_action']} | Reason: {r['reason']}"
    )
    print("    => Alice gets a full refund of $199.99")

    h("SCENARIO 2: Too Late - Return window exceeded")
    p("Customer Alice (CUST-001) bought electronics 45 days ago. Policy is 30 days.")
    p("> python cli.py check ORD-002 CUST-001")
    r = await check_return("ORD-002", "CUST-001")
    print(
        f"    [FAIL] Eligible: {r['eligible']} | Action: {r['recommended_action']} | Reason: {r['reason']}"
    )
    print("    => Alice cannot return this item.")

    h("SCENARIO 3: Damaged Item - Replacement instead of refund")
    p("Customer Charlie (CUST-003) bought clothing 10 days ago. Arrived damaged.")
    p("> python cli.py check ORD-004 CUST-003")
    r = await check_return("ORD-004", "CUST-003")
    print(
        f"    [PASS] Eligible: {r['eligible']} | Action: {r['recommended_action']} | Reason: {r['reason']}"
    )
    print("    => Charlie gets a replacement shipped immediately.")

    h("SCENARIO 4: Excluded Item - Digital goods can't be returned")
    p("Customer Bob (CUST-002) bought a digital download 5 days ago.")
    p("> python cli.py check ORD-003 CUST-002")
    r = await check_return("ORD-003", "CUST-002")
    print(
        f"    [FAIL] Eligible: {r['eligible']} | Action: {r['recommended_action']} | Reason: {r['reason']}"
    )
    print("    => Bob's item is excluded (digital_goods).")

    h("SCENARIO 5: Fraud Flag - Blocked immediately")
    p("Customer Dave (CUST-004) has a chargeback history. Trying to return a $150 item.")
    p("> python cli.py check ORD-005 CUST-004")
    r = await check_return("ORD-005", "CUST-004")
    print(
        f"    [FAIL] Eligible: {r['eligible']} | Action: {r['recommended_action']} | Fraud: {r['fraud_signal']}"
    )
    print("    => Dave's request rejected due to fraud_flag.")

    h("SCENARIO 6: Fraud DB Match - Escalate for human review")
    p("Customer Eve (CUST-005) has no fraud flag but matched a suspicious pattern in DB.")
    p("> python cli.py check ORD-006 CUST-005")
    r = await check_return("ORD-006", "CUST-005")
    print(
        f"    [FLAG] Eligible: {r['eligible']} | Action: {r['recommended_action']} | Fraud: {r['fraud_signal']}"
    )
    print("    => Eve's case escalated to a human agent for review.")

    h("SCENARIO 7: Order Not Found")
    p("Non-existent order ID.")
    p("> python cli.py check ORD-999 CUST-001")
    r = await check_return("ORD-999", "CUST-001")
    print(f"    [ERR] {r['error']}")

    h("SCENARIO 8: Customer Not Found")
    p("Non-existent customer ID.")
    p("> python cli.py check ORD-001 CUST-999")
    r = await check_return("ORD-001", "CUST-999")
    print(f"    [ERR] {r['error']}")

    h("SCENARIO 9: Order-Customer Mismatch")
    p("Alice (CUST-001) tries to return Bob's (CUST-002) order.")
    p("> python cli.py check ORD-001 CUST-002")
    r = await check_return("ORD-001", "CUST-002")
    print(f"    [ERR] {r['error']}")

    h("SCENARIO 10: Excluded - Perishables")
    p("Alice (CUST-001) bought strawberries 2 days ago. Perishables are excluded.")
    p("> python cli.py check ORD-007 CUST-001")
    r = await check_return("ORD-007", "CUST-001")
    print(f"    [FAIL] Eligible: {r['eligible']} | Exclusion: {r['exclusion_reason']}")

    h("SCENARIO 11: Same Day - 0 days since purchase")
    p("Priya (CUST-003) just bought a mouse today. Full refund available.")
    p("> python cli.py check ORD-008 CUST-003")
    r = await check_return("ORD-008", "CUST-003")
    print(
        f"    [PASS] Eligible: {r['eligible']} | Days: {r['days_since_purchase']} | Action: {r['recommended_action']}"
    )

    h("SCENARIO 12: Exactly 30 days - boundary")
    p("Priya (CUST-003) bought a USB cable exactly 30 days ago.")
    p("> python cli.py check ORD-009 CUST-003")
    r = await check_return("ORD-009", "CUST-003")
    print(
        f"    [PASS] Eligible: {r['eligible']} | Days: {r['days_since_purchase']} | Action: {r['recommended_action']}"
    )

    h("SCENARIO 13: New Customer - Clean return")
    p("Marcus (CUST-006) bought a towel set 12 days ago. Clean account.")
    p("> python cli.py check ORD-010 CUST-006")
    r = await check_return("ORD-010", "CUST-006")
    print(f"    [PASS] Eligible: {r['eligible']} | Action: {r['recommended_action']}")

    h("SCENARIO 14: Damaged Item - Replacement")
    p("Alice (CUST-001) bought face cream 25 days ago. Arrived damaged.")
    p("> python cli.py check ORD-012 CUST-001")
    r = await check_return("ORD-012", "CUST-001")
    print(
        f"    [PASS] Eligible: {r['eligible']} | Action: {r['recommended_action']} | Reason: {r['reason']}"
    )

    h("SCENARIO 15: New Fraud Account - Blocked")
    p("Vladimir (CUST-007) has multiple chargebacks. Order is within window.")
    p("> python cli.py check ORD-013 CUST-007")
    r = await check_return("ORD-013", "CUST-007")
    print(
        f"    [FAIL] Eligible: {r['eligible']} | Fraud: {r['fraud_signal']} | Action: {r['recommended_action']}"
    )

    h("SCENARIO 16: Final Sale - Excluded")
    p("Marcus (CUST-006) bought a final sale rug yesterday. No returns.")
    p("> python cli.py check ORD-014 CUST-006")
    r = await check_return("ORD-014", "CUST-006")
    print(f"    [FAIL] Eligible: {r['eligible']} | Exclusion: {r['exclusion_reason']}")

    h("SCENARIO 17: Fraud DB Match - Escalate")
    p("Yuki (CUST-008) matched a velocity check in fraud DB. No fraud flag on account.")
    p("> python cli.py check ORD-015 CUST-008")
    r = await check_return("ORD-015", "CUST-008")
    print(
        f"    [FLAG] Eligible: {r['eligible']} | Fraud: {r['fraud_signal']} | Action: {r['recommended_action']}"
    )


async def demo_guardrails():
    h("GUARDRAIL DEMO: PII Scrubber")
    p("Customer sends a message with their credit card number:")
    p("> python cli.py guardrail pii 'My card is 4111-1111-1111-1111'")
    r = await scrub_pii(None, None, "My card is 4111-1111-1111-1111")
    print(f"    Triggered: {r.tripwire_triggered}")
    print(f"    Scrubbed:  {r.output_info['scrubbed_message']}")

    p("\nCustomer sends a message with their SSN:")
    p("> python cli.py guardrail pii 'My SSN is 123-45-6789'")
    r = await scrub_pii(None, None, "My SSN is 123-45-6789")
    print(f"    Triggered: {r.tripwire_triggered}")
    print(f"    Scrubbed:  {r.output_info['scrubbed_message']}")

    p("\nClean message - no PII:")
    p("> python cli.py guardrail pii 'I want to check my order status'")
    r = await scrub_pii(None, None, "I want to check my order status")
    print(f"    Triggered: {r.tripwire_triggered}")
    print("    Passed through unchanged.")

    h("GUARDRAIL DEMO: Sentiment Monitor")
    p("Angry customer threatening legal action:")
    p("> python cli.py guardrail sentiment 'I WILL SUE YOU!!!'")
    r = await score_sentiment(None, None, "I WILL SUE YOU!!!")
    print(f"    Score: {r.output_info['score']} | Escalate: {r.output_info['escalate']}")
    print(f"    => {'ESCALATED' if r.output_info['escalate'] else 'OK - within threshold'}")

    p("\nFurious customer with profanity:")
    p("> python cli.py guardrail sentiment 'This is f***ing unacceptable! I want a manager NOW!'")
    r = await score_sentiment(None, None, "This is fucking unacceptable! I want a manager NOW!")
    print(f"    Score: {r.output_info['score']} | Escalate: {r.output_info['escalate']}")
    print(f"    => {'ESCALATED' if r.output_info['escalate'] else 'OK - within threshold'}")

    p("\nNeutral customer:")
    p("> python cli.py guardrail sentiment 'Hi, can you tell me when my order will arrive?'")
    r = await score_sentiment(None, None, "Hi, can you tell me when my order will arrive?")
    print(f"    Score: {r.output_info['score']} | Escalate: {r.output_info['escalate']}")

    h("GUARDRAIL DEMO: Refund Cap")
    p("Resolution agent tries to issue a $600 refund (cap is $500):")
    p("> python cli.py guardrail refund 600")
    r = await check_refund_cap(None, None, {"refund_amount": 600})
    print(f"    Triggered: {r.tripwire_triggered}")
    print(f"    Output: {json.dumps(r.output_info, indent=4)}")
    print("    => Blocked! Human approval required.")

    p("\nResolution agent issues a $200 refund (under cap):")
    p("> python cli.py guardrail refund 200")
    r = await check_refund_cap(None, None, {"refund_amount": 200})
    print(f"    Triggered: {r.tripwire_triggered}")
    print("    => Passed through.")


async def main():
    print("=" * 60)
    print("  Agent 01 - Customer Support System Demo")
    print("=" * 60)
    await demo_policy()
    await demo_guardrails()
    print(f"\n{'=' * 60}")
    print("  Demo complete! See test queries below.")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    asyncio.run(main())
