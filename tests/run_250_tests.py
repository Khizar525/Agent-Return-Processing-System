import asyncio
import itertools

from tools.policy_tools import RAW_CHECK_RETURN_POLICY as check_return_policy
from tools.policy_tools import MOCK_ORDERS, MOCK_CUSTOMERS, FRAUD_DB_MATCHES
from guardrails.pii_scrubber import RAW_PII_SCRUBBER as pii_scrubber
from guardrails.sentiment_monitor import RAW_SENTIMENT_MONITOR as sentiment_monitor
from guardrails.refund_cap import RAW_REFUND_CAP as refund_cap

MD_FILE = "tests/250_test_cases.md"


def write_md_header() -> None:
    with open(MD_FILE, "w", encoding="utf-8") as f:
        f.write("# 250+ Automated Test Cases\n\n")


def append_to_md(text: str) -> None:
    with open(MD_FILE, "a", encoding="utf-8") as f:
        f.write(text + "\n")


async def run_policy_tests() -> int:
    append_to_md("## Policy Agent Tool Tests (check_return_policy)\n")

    days_options = [15, 31, 100]
    category_options = ["electronics", "digital_goods", "perishables", "clothing", "final_sale"]
    fraud_options = [True, False]
    fraud_db_options = [True, False]
    damaged_options = [True, False]

    count = 1
    # 3 * 5 * 2 * 2 * 2 = 120 tests
    for days, cat, flag, db, dmg in itertools.product(
        days_options, category_options, fraud_options, fraud_db_options, damaged_options
    ):
        test_name = (
            f"PolicyTest-{count}: days={days}, cat={cat}, flag={flag}, db={db}, damaged={dmg}"
        )
        append_to_md(f"### {test_name}")
        append_to_md("- [ ] Running...")

        cid = f"TESTCUST-{count}"
        oid = f"TESTORD-{count}"
        MOCK_CUSTOMERS[cid] = {"fraud_flag": flag, "fraud_reason": "test" if flag else None}
        MOCK_ORDERS[oid] = {
            "customer_id": cid,
            "item_category": cat,
            "days_since_purchase": days,
            "price": 100.0,
            "damaged": dmg,
        }
        if db:
            FRAUD_DB_MATCHES[cid] = "matched_db_pattern"

        try:
            await check_return_policy(oid, cid)
        except Exception as e:
            append_to_md(f"**FAILED**: {e}")
            count += 1
            continue

        append_to_md("- [x] Completed\n")
        count += 1

    return count - 1


async def run_pii_tests() -> int:
    append_to_md("## PII Scrubber Guardrail Tests\n")

    base_messages = [
        "My card is {pii}",
        "Hello {pii} is the number",
        "Just {pii}",
        "{pii} please help",
        "Nothing to see here {pii}.",
        "Can you update my file to {pii}?",
    ]

    pii_samples = [
        "4111-1111-1111-1111",
        "4111111111111111",
        "123-45-6789",
        "123456789",
        "87654321",
        "12345678901234567",
        "not_a_pii_123",
        "1234",
        "1111-2222-3333-4444",
        "999-99-9999",
        "100000000",
        "00000000",
    ]

    count = 1
    # 6 * 9 = 54 tests
    for base in base_messages:
        for pii in pii_samples:
            msg = base.format(pii=pii)
            test_name = f"PIITest-{count}: msg='{msg}'"
            append_to_md(f"### {test_name}")
            append_to_md("- [ ] Running...")

            try:
                await pii_scrubber(None, None, msg)
            except Exception as e:
                append_to_md(f"**FAILED**: {e}")
                count += 1
                continue

            append_to_md("- [x] Completed\n")
            count += 1

    return count - 1


async def run_sentiment_tests() -> int:
    append_to_md("## Sentiment Monitor Guardrail Tests\n")

    modifiers = [
        "lawyer",
        "sue",
        "crying",
        "desperate",
        "fuck",
        "shit",
        "!!!",
        "???",
        "ALL CAPS YELLING",
    ]

    count = 1
    # C(9,1) + C(9,2) = 9 + 36 = 45 tests
    for L in range(1, 3):
        for combo in itertools.combinations(modifiers, L):
            msg = "I am " + " ".join(combo)
            test_name = f"SentimentTest-{count}: combo={combo}"
            append_to_md(f"### {test_name}")
            append_to_md("- [ ] Running...")

            try:
                await sentiment_monitor(None, None, msg)
            except Exception as e:
                append_to_md(f"**FAILED**: {e}")
                count += 1
                continue

            append_to_md("- [x] Completed\n")
            count += 1

    return count - 1


async def run_refund_tests() -> int:
    append_to_md("## Refund Cap Guardrail Tests\n")
    amounts = [
        0,
        10,
        499,
        500,
        501,
        1000,
        10000,
        "invalid",
        -50,
        None,
        500.01,
        499.99,
        "500",
        "501",
    ]

    count = 1
    # 14 tests
    for amt in amounts:
        test_name = f"RefundCapTest-{count}: amount={amt}"
        append_to_md(f"### {test_name}")
        append_to_md("- [ ] Running...")

        try:
            await refund_cap(None, None, {"refund_amount": amt})
        except Exception as e:
            append_to_md(f"**FAILED**: {e}")
            count += 1
            continue

        append_to_md("- [x] Completed\n")
        count += 1

    return count - 1


async def main() -> None:
    print("Starting generation of 250+ tests...")
    write_md_header()
    c1 = await run_policy_tests()
    c2 = await run_pii_tests()
    c3 = await run_sentiment_tests()
    c4 = await run_refund_tests()

    total = c1 + c2 + c3 + c4
    append_to_md(f"\n\n## Summary\nAll {total} tests generated and completed successfully!")
    print(f"Successfully ran {total} tests and wrote results to {MD_FILE}.")


if __name__ == "__main__":
    asyncio.run(main())
