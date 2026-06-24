# Test Suite Report — Agent-Return-Processing-System

> **Generated:** 2026-06-24  
> **Result:** 353 passed, 0 skipped, 0 failed  
> **Total:** 353 tests across 9 test files

---

## Summary

| File | Passed | Skipped | Failed | Owner |
|---|---|---|---|---|
| `test_policy_agent.py` | 106 | 0 | 0 | M2 |
| `test_resolution_agent.py` | 21 | 0 | 0 | M3 |
| `test_billing_agent.py` | 18 | 0 | 0 | Lead |
| `test_comm_escalation.py` | 14 | 0 | 0 | M4 |
| `test_database.py` | 37 | 0 | 0 | Lead |
| `test_infra_observability.py` | 41 | 0 | 0 | M5 |
| `test_tools.py` | 44 | 0 | 0 | M3 |
| `test_integration.py` | 40 | 0 | 0 | Lead |
| `test_tracking_tools.py` | 32 | 0 | 0 | Lead |
| **Total** | **353** | **0** | **0** | |

---

## 1. `tests/test_policy_agent.py` — 106 passed (M2)

### TestNominalPaths (6 tests)
| # | Test | Status | What it tests |
|---|---|---|---|
| 1 | `test_eligible_refund` | ✅ PASSED | ORD-002/CUST-001: within window, eligible → refund |
| 2 | `test_eligible_replacement` | ✅ PASSED | ORD-004/CUST-003: damaged item → replacement |
| 3 | `test_ineligible_outside_window` | ✅ PASSED | ORD-001/CUST-001: 31 days > 30-day limit |
| 4 | `test_ineligible_excluded_category` | ✅ PASSED | ORD-003/CUST-002: digital goods excluded |
| 5 | `test_fraud_flag_escalate` | ✅ PASSED | ORD-005/CUST-004: fraud flag → escalate |
| 6 | `test_fraud_db_match_escalate` | ✅ PASSED | ORD-006/CUST-005: fraud DB match → escalate |

### TestBoundaryCases (5 tests)
| # | Test | Status | What it tests |
|---|---|---|---|
| 7 | `test_exactly_30_days` | ✅ PASSED | Boundary: exactly 30 days = eligible |
| 8 | `test_excluded_all_categories_covered` | ✅ PASSED | All 3 excluded categories tested |
| 9 | `test_all_four_actions_producible` | ✅ PASSED | All 4 recommended_actions reachable |
| 10 | `test_days_since_purchase_beyond_extreme` | ✅ PASSED | 999,999 days since purchase |
| 11 | `test_zero_days_since_purchase` | ✅ PASSED | 0 days = eligible |

### TestErrorPaths (13 tests)
| # | Test | Status | What it tests |
|---|---|---|---|
| 12 | `test_order_not_found` | ✅ PASSED | Unknown order → error |
| 13 | `test_customer_not_found` | ✅ PASSED | Unknown customer → error |
| 14 | `test_both_not_found` | ✅ PASSED | Both unknown → error |
| 15 | `test_order_customer_mismatch` | ✅ PASSED | Order belongs to different customer |
| 16 | `test_empty_order_id` | ✅ PASSED | Empty string order_id |
| 17 | `test_empty_customer_id` | ✅ PASSED | Empty string customer_id |
| 18 | `test_whitespace_order_id` | ✅ PASSED | Whitespace-only order_id |
| 19 | `test_whitespace_customer_id` | ✅ PASSED | Whitespace-only customer_id |
| 20 | `test_special_chars_in_order_id` | ✅ PASSED | XSS/injection in order_id |
| 21 | `test_order_id_with_newline` | ✅ PASSED | Newline in order_id |
| 22 | `test_very_long_order_id` | ✅ PASSED | 10,000 char order_id |
| 23 | `test_error_dict_has_success_field` | ✅ PASSED | Error returns include `success: False` |
| 24 | `test_success_dict_has_success_field` | ✅ PASSED | Success returns include `success: True` |

### TestCompoundViolations (4 tests)
| # | Test | Status | What it tests |
|---|---|---|---|
| 25 | `test_outside_window_and_excluded` | ✅ PASSED | Window + excluded category |
| 26 | `test_outside_window_and_fraud_flag` | ✅ PASSED | Window + fraud flag |
| 27 | `test_excluded_and_fraud_db_match` | ✅ PASSED | Excluded + fraud DB |
| 28 | `test_all_violations_at_once` | ✅ PASSED | Window + excluded + fraud flag |

### TestOutputContract (8 tests)
| # | Test | Status | What it tests |
|---|---|---|---|
| 29 | `test_all_contract_keys_present_success` | ✅ PASSED | All 10 keys in success response |
| 30 | `test_all_contract_keys_present_error` | ✅ PASSED | All 10 keys in error response |
| 31 | `test_field_types_success` | ✅ PASSED | Correct types for all fields |
| 32 | `test_recommended_action_is_valid` | ✅ PASSED | One of 4 allowed values |
| 33 | `test_error_field_type` | ✅ PASSED | error is str or None |
| 34 | `test_fraud_signal_bool_only` | ✅ PASSED | fraud_signal is always bool |
| 35 | `test_return_window_days_positive` | ✅ PASSED | > 0 |
| 36 | `test_days_since_purchase_non_negative` | ✅ PASSED | >= 0 |

### TestIdempotencyAndMutation (3 tests)
| # | Test | Status | What it tests |
|---|---|---|---|
| 37 | `test_repeatable_calls_return_same` | ✅ PASSED | Same input → same output |
| 38 | `test_calls_dont_mutate_mock_data` | ✅ PASSED | No side effects |
| 39 | `test_concurrent_calls_dont_interfere` | ✅ PASSED | asyncio.gather safety |

### TestPiiScrubber (19 tests)
| # | Test | Status | What it tests |
|---|---|---|---|
| 40 | `test_credit_card_dashed` | ✅ PASSED | 1234-5678-9012-3456 redacted |
| 41 | `test_credit_card_undashed` | ✅ PASSED | 1234567890123456 redacted |
| 42 | `test_credit_card_with_spaces` | ✅ PASSED | 1234 5678 9012 3456 redacted |
| 43 | `test_credit_card_mixed_delimiters` | ✅ PASSED | Mixed formats |
| 44 | `test_ssn_dashed` | ✅ PASSED | 123-45-6789 redacted |
| 45 | `test_ssn_undashed` | ✅ PASSED | 123456789 redacted |
| 46 | `test_bank_account_8_digits` | ✅ PASSED | 8-digit account redacted |
| 47 | `test_bank_account_17_digits` | ✅ PASSED | 17-digit account redacted |
| 48 | `test_multiple_pii_in_message` | ✅ PASSED | Multiple PII types in one message |
| 49 | `test_pii_at_start_of_message` | ✅ PASSED | PII at beginning |
| 50 | `test_pii_at_end_of_message` | ✅ PASSED | PII at end |
| 51 | `test_clean_message_passes_through` | ✅ PASSED | No PII → no change |
| 52 | `test_empty_message` | ✅ PASSED | Empty string |
| 53 | `test_very_long_message_with_pii` | ✅ PASSED | Long message with PII |
| 54 | `test_7_digit_number_not_redacted` | ✅ PASSED | 7 digits = not PII |
| 55 | `test_numbers_with_letters_not_redacted` | ✅ PASSED | Alphanumeric not PII |
| 56 | `test_pii_with_unicode` | ✅ PASSED | Unicode characters |
| 57 | `test_message_with_only_numbers` | ✅ PASSED | All numbers |
| 58 | `test_guardrail_output_contract` | ✅ PASSED | Output has required keys |

### TestSentimentMonitor (16 tests)
| # | Test | Status | What it tests |
|---|---|---|---|
| 59 | `test_legal_keywords_and_all_caps` | ✅ PASSED | "I WILL SUE" → score 0.9, escalate |
| 60 | `test_above_threshold_escalates` | ✅ PASSED | Combined signals > 0.8 → escalate |
| 61 | `test_neutral_message_no_trigger` | ✅ PASSED | Normal message → pass |
| 62 | `test_empty_message` | ✅ PASSED | Empty → pass |
| 63 | `test_all_caps_short_ignored` | ✅ PASSED | Short caps ignored |
| 64 | `test_boundary_exactly_threshold` | ✅ PASSED | Score 0.9 → escalate (>= threshold) |
| 65 | `test_profanity_only` | ✅ PASSED | Profanity detected |
| 66 | `test_multiple_exclamation_marks` | ✅ PASSED | "!!!" → escalation |
| 67 | `test_many_exclamation_marks_capped` | ✅ PASSED | Score capped at 1.0 |
| 68 | `test_score_capped_at_1_0` | ✅ PASSED | Never > 1.0 |
| 69 | `test_unicode_message` | ✅ PASSED | Unicode characters |
| 70 | `test_numbers_only_message` | ✅ PASSED | All numbers |
| 71 | `test_single_word_message` | ✅ PASSED | Single word |
| 72 | `test_very_long_message` | ✅ PASSED | Long message |
| 73 | `test_question_marks_only` | ✅ PASSED | "???" |
| 74 | `test_guardrail_output_dict_keys` | ✅ PASSED | Output has required keys |

### TestRefundCap (13 tests)
| # | Test | Status | What it tests |
|---|---|---|---|
| 75 | `test_above_cap_blocked` | ✅ PASSED | $600 > $500 → blocked |
| 76 | `test_below_cap_passes` | ✅ PASSED | $400 < $500 → pass |
| 77 | `test_exactly_at_cap_passes` | ✅ PASSED | $500 = $500 → pass |
| 78 | `test_zero_refund_passes` | ✅ PASSED | $0 → pass |
| 79 | `test_negative_refund_passes` | ✅ PASSED | -$100 → pass |
| 80 | `test_missing_refund_amount_passes` | ✅ PASSED | No amount → pass |
| 81 | `test_none_output_passes` | ✅ PASSED | None → pass |
| 82 | `test_very_large_refund_blocked` | ✅ PASSED | $999,999 → blocked |
| 83 | `test_refund_cap_is_positive` | ✅ PASSED | Cap > 0 |
| 84 | `test_refund_amount_as_string` | ✅ PASSED | String "$600" → blocked |
| 85 | `test_refund_amount_unparseable_string` | ✅ PASSED | "abc" → pass |
| 86 | `test_multiple_output_keys_unchanged` | ✅ PASSED | Other keys untouched |
| 87 | `test_guardrail_output_contract` | ✅ PASSED | Output has required keys |

### TestPolicyAgent (9 tests)
| # | Test | Status | What it tests |
|---|---|---|---|
| 88 | `test_agent_name` | ✅ PASSED | Name = "PolicyAgent" |
| 89 | `test_agent_model` | ✅ PASSED | Model = "openai/gpt-oss-120b:free" |
| 90 | `test_agent_has_tools` | ✅ PASSED | Has check_return_policy tool |
| 91 | `test_agent_instructions_not_empty` | ✅ PASSED | Instructions exist |
| 92 | `test_agent_instructions_mention_json_output` | ✅ PASSED | Instructions mention JSON |
| 93 | `test_agent_instructions_mention_eligible` | ✅ PASSED | Instructions mention eligible |
| 94 | `test_agent_instructions_mention_check_return_policy` | ✅ PASSED | Instructions mention tool |
| 95 | `test_agent_tools_contains_check_return_policy` | ✅ PASSED | Tool in tools list |
| 96 | `test_agent_no_handoffs` | ✅ PASSED | No handoffs configured |

### TestCrossContractCompliance (5 tests)
| # | Test | Status | What it tests |
|---|---|---|---|
| 97 | `test_all_tools_async` | ✅ PASSED | All tool functions are async |
| 98 | `test_check_return_policy_function_tool_decorated` | ✅ PASSED | @function_tool decorator |
| 99 | `test_no_unhandled_exceptions_on_any_input` | ✅ PASSED | No crashes on any input |
| 100 | `test_exclusion_list_is_set` | ✅ PASSED | EXCLUDED_CATEGORIES is a set |
| 101 | `test_return_window_days_default` | ✅ PASSED | Default = 30 |

### TestDemoIntegration (5 tests)
| # | Test | Status | What it tests |
|---|---|---|---|
| 102 | `test_demo_scenario_1_alice` | ✅ PASSED | Alice: eligible refund |
| 103 | `test_demo_scenario_2_bob_excluded` | ✅ PASSED | Bob: excluded digital goods |
| 104 | `test_demo_scenario_3_charlie_damaged` | ✅ PASSED | Charlie: damaged replacement |
| 105 | `test_demo_scenario_4_dave_fraud` | ✅ PASSED | Dave: fraud flag → escalate |
| 106 | `test_demo_scenario_5_eve_escalate` | ✅ PASSED | Eve: fraud DB → escalate |

---

## 2. `tests/test_resolution_agent.py` — 21 passed (M3)

### Agent Definition Tests (9 tests)
| # | Test | Status | What it tests |
|---|---|---|---|
| 107 | `test_agent_name` | ✅ PASSED | Name = "ResolutionAgent" |
| 108 | `test_agent_has_correct_model` | ✅ PASSED | Model = "openai/gpt-oss-120b:free" |
| 109 | `test_agent_has_all_three_tools` | ✅ PASSED | 3 tools: refund, label, replacement |
| 110 | `test_agent_tools_are_function_tool_instances` | ✅ PASSED | All are @function_tool |
| 111 | `test_agent_has_refund_cap_guardrail` | ✅ PASSED | output_guardrails wired |
| 112 | `test_agent_instructions_mention_refund` | ✅ PASSED | Instructions mention refund |
| 113 | `test_agent_instructions_mention_label` | ✅ PASSED | Instructions mention label |
| 114 | `test_agent_instructions_mention_replacement` | ✅ PASSED | Instructions mention replacement |
| 115 | `test_agent_instructions_mention_500` | ✅ PASSED | Instructions mention $500 cap |

### Tool Invocation Tests (3 tests)
| # | Test | Status | What it tests |
|---|---|---|---|
| 116 | `test_process_refund_returns_dict_with_success_key` | ✅ PASSED | Refund returns success key |
| 117 | `test_process_refund_empty_order_id` | ✅ PASSED | Empty order_id → error |
| 118 | `test_process_refund_unsupported_method` | ✅ PASSED | Unknown method → error |

### Fixture Tests (3 tests)
| # | Test | Status | What it tests |
|---|---|---|---|
| 119 | `test_resolution_fixture_has_resolution_agent_cases` | ✅ PASSED | Fixtures have resolution cases |
| 120 | `test_resolution_fixture_refund_cap_case` | ✅ PASSED | Fixtures have cap case |
| 121 | `test_resolution_fixture_happy_path` | ✅ PASSED | Fixtures have happy path |

### E2E Autonomous Tests (6 tests)
| # | Test | Status | What it tests |
|---|---|---|---|
| 122 | `test_agent_autonomous_refund_success` | ✅ PASSED | Full refund flow |
| 123 | `test_agent_refund_cap_enforcement_above_limit` | ✅ PASSED | $600 blocked by guardrail |
| 124 | `test_agent_graceful_api_failure_handling` | ✅ PASSED | API error → graceful response |
| 125 | `test_agent_autonomous_replacement_success` | ✅ PASSED | Full replacement flow |
| 126 | `test_agent_autonomous_label_success` | ✅ PASSED | Full label flow |
| 127 | `test_agent_autonomous_sequencing` | ✅ PASSED | Refund + label sequence |

---

## 3. `tests/test_billing_agent.py` — 18 passed (Lead)

### Agent Definition Tests (8 tests)
| # | Test | Status | What it tests |
|---|---|---|---|
| 128 | `test_agent_name` | ✅ PASSED | Name = "BillingAgent" |
| 129 | `test_agent_has_correct_model` | ✅ PASSED | Model = "openai/gpt-oss-120b:free" |
| 130 | `test_agent_has_process_refund_tool` | ✅ PASSED | Has process_refund tool |
| 131 | `test_agent_has_refund_cap_guardrail` | ✅ PASSED | output_guardrails wired |
| 132 | `test_agent_has_output_type` | ✅ PASSED | output_type = BillingDecision |
| 133 | `test_agent_instructions_mention_billing` | ✅ PASSED | Instructions mention billing |
| 134 | `test_agent_instructions_mention_refund_cap` | ✅ PASSED | Instructions mention refund cap |
| 135 | `test_agent_instructions_mention_duplicate` | ✅ PASSED | Instructions mention duplicate |

### Schema Tests (5 tests)
| # | Test | Status | What it tests |
|---|---|---|---|
| 136 | `test_all_fields_present` | ✅ PASSED | All fields in BillingDecision |
| 137 | `test_valid_refund_decision` | ✅ PASSED | Valid refund decision |
| 138 | `test_valid_reject_decision` | ✅ PASSED | Valid reject decision |
| 139 | `test_valid_escalate_decision` | ✅ PASSED | Valid escalate decision |
| 140 | `test_recommended_action_is_valid` | ✅ PASSED | One of 3 allowed values |

### Tool Tests (3 tests)
| # | Test | Status | What it tests |
|---|---|---|---|
| 141 | `test_process_refund_success` | ✅ PASSED | Refund succeeds |
| 142 | `test_process_refund_empty_order_id` | ✅ PASSED | Empty order_id → error |
| 143 | `test_process_refund_unsupported_method` | ✅ PASSED | Unknown method → error |

### Refund Cap Tests (2 tests)
| # | Test | Status | What it tests |
|---|---|---|---|
| 144 | `test_guardrail_allows_under_cap_direct` | ✅ PASSED | Under cap → allowed |
| 145 | `test_cap_enforcement_exists` | ✅ PASSED | Guardrail wired |

---

## 4. `tests/test_comm_escalation.py` — 14 passed (M4)

### Notification Tests (4 tests)
| # | Test | Status | What it tests |
|---|---|---|---|
| 146 | `test_send_notification_email_success` | ✅ PASSED | Email notification works |
| 147 | `test_send_notification_sms_success` | ✅ PASSED | SMS notification works |
| 148 | `test_send_notification_email_to_sms_fallback` | ✅ PASSED | Email fallback to SMS |
| 149 | `test_draft_and_send_function` | ✅ PASSED | Draft and send works |

### Brand Voice Tests (3 tests)
| # | Test | Status | What it tests |
|---|---|---|---|
| 150 | `test_brand_voice_blocks_prohibited_language` | ✅ PASSED | Prohibited language blocked |
| 151 | `test_brand_voice_allows_clean_messages` | ✅ PASSED | Clean messages pass |
| 152 | `test_brand_voice_enforces_150_word_limit` | ✅ PASSED | 150-word limit enforced |

### Agent Tests (4 tests)
| # | Test | Status | What it tests |
|---|---|---|---|
| 153 | `test_communication_agent_uses_correct_model` | ✅ PASSED | Model = "openai/gpt-oss-120b:free" |
| 154 | `test_draft_and_send_with_hybrid_llm_function` | ✅ PASSED | Hybrid LLM function works |
| 155 | `test_handle_escalation_function` | ✅ PASSED | Escalation handler works |
| 156 | `test_handle_escalation_with_hybrid_llm_function` | ✅ PASSED | Hybrid escalation works |

### Escalation Tests (3 tests)
| # | Test | Status | What it tests |
|---|---|---|---|
| 157 | `test_escalation_agent_instructions` | ✅ PASSED | Instructions present |
| 158 | `test_create_human_ticket` | ✅ PASSED | Ticket creation works |
| 159 | `test_log_resolution` | ✅ PASSED | Resolution logging works |

---

## 5. `tests/test_database.py` — 37 passed (Lead)

### TestOrderDTO (4 tests)
| # | Test | Status | What it tests |
|---|---|---|---|
| 160 | `test_construction` | ✅ PASSED | DTO construction |
| 161 | `test_damaged_order` | ✅ PASSED | Damaged order DTO |
| 162 | `test_zero_days` | ✅ PASSED | Zero days since purchase |
| 163 | `test_negative_price` | ✅ PASSED | Negative price handling |

### TestCustomerDTO (3 tests)
| # | Test | Status | What it tests |
|---|---|---|---|
| 164 | `test_construction_no_fraud` | ✅ PASSED | Customer without fraud |
| 165 | `test_construction_with_fraud` | ✅ PASSED | Customer with fraud flag |
| 166 | `test_construction` | ✅ PASSED | FraudDbMatch DTO |

### TestMemoryBackend (18 tests)
| # | Test | Status | What it tests |
|---|---|---|---|
| 167 | `test_get_order_exists` | ✅ PASSED | Get existing order |
| 168 | `test_get_order_not_found` | ✅ PASSED | Get missing order |
| 169 | `test_get_order_empty_string` | ✅ PASSED | Empty string order |
| 170 | `test_get_order_all_default_records` | ✅ PASSED | All default records |
| 171 | `test_get_customer_exists` | ✅ PASSED | Get existing customer |
| 172 | `test_get_customer_fraud_flag` | ✅ PASSED | Customer with fraud |
| 173 | `test_get_customer_not_found` | ✅ PASSED | Get missing customer |
| 174 | `test_get_customer_empty_string` | ✅ PASSED | Empty string customer |
| 175 | `test_get_fraud_db_match_exists` | ✅ PASSED | Get fraud match |
| 176 | `test_get_fraud_db_match_not_found` | ✅ PASSED | Get missing fraud match |
| 177 | `test_get_fraud_db_match_no_flag_customer` | ✅ PASSED | No flag customer |
| 178 | `test_set_order_updates_field` | ✅ PASSED | Update order field |
| 179 | `test_set_order_nonexistent` | ✅ PASSED | Set missing order |
| 180 | `test_set_customer_updates_field` | ✅ PASSED | Update customer field |
| 181 | `test_set_customer_nonexistent` | ✅ PASSED | Set missing customer |
| 182 | `test_close` | ✅ PASSED | Close backend |
| 183 | `test_custom_data` | ✅ PASSED | Custom data loading |
| 184 | `test_empty_data` | ✅ PASSED | Empty data handling |
| 185 | `test_none_data_uses_default` | ✅ PASSED | None data fallback |

### TestFileBackend (9 tests)
| # | Test | Status | What it tests |
|---|---|---|---|
| 186 | `test_loads_from_file` | ✅ PASSED | Load from file |
| 187 | `test_creates_default_if_missing` | ✅ PASSED | Create default file |
| 188 | `test_get_order_not_found` | ✅ PASSED | Get missing order |
| 189 | `test_get_customer` | ✅ PASSED | Get customer |
| 190 | `test_get_customer_not_found` | ✅ PASSED | Get missing customer |
| 191 | `test_get_fraud_db_match` | ✅ PASSED | Get fraud match |
| 192 | `test_get_fraud_db_match_not_found` | ✅ PASSED | Get missing fraud match |
| 193 | `test_close_resets_cache` | ✅ PASSED | Close resets cache |
| 194 | `test_caches_data` | ✅ PASSED | Data caching |

### TestFactory (2 tests)
| # | Test | Status | What it tests |
|---|---|---|---|
| 195 | `test_create_repository_returns_repository` | ✅ PASSED | Factory returns Repository |
| 196 | `test_file_backend_default` | ✅ PASSED | Default is FileBackend |

---

## 6. `tests/test_infra_observability.py` — 41 passed (M5)

### TestKafkaConfig (12 tests)
| # | Test | Status | What it tests |
|---|---|---|---|
| 197 | `test_validate_message_valid` | ✅ PASSED | Valid message passes |
| 198 | `test_validate_message_missing_field` | ✅ PASSED | Missing required field |
| 199 | `test_validate_message_wrong_type` | ✅ PASSED | Wrong field type |
| 200 | `test_validate_message_session_id_wrong_type` | ✅ PASSED | Session ID wrong type |
| 201 | `test_validate_message_none_session_id_valid` | ✅ PASSED | None session_id is valid |
| 202 | `test_build_message` | ✅ PASSED | Message builder works |
| 203 | `test_build_message_with_session_id` | ✅ PASSED | Message with session_id |
| 204 | `test_resolve_topic` | ✅ PASSED | Topic resolution works |
| 205 | `test_resolve_topic_missing_env` | ✅ PASSED | Missing env var → error |
| 206 | `test_resolve_topic_invalid_channel` | ✅ PASSED | Invalid channel → error |
| 207 | `test_forward_message_success` | ✅ PASSED | Webhook forwarding works |
| 208 | `test_forward_message_http_error` | ✅ PASSED | HTTP error handling |

### TestDatadogSetup (8 tests)
| # | Test | Status | What it tests |
|---|---|---|---|
| 209 | `test_configure_datadog_disabled_when_no_key` | ✅ PASSED | Disabled without API key |
| 210 | `test_configure_datadog_enabled` | ✅ PASSED | Enabled with API key |
| 211 | `test_agent_span_disabled_when_no_tracer` | ✅ PASSED | Span disabled |
| 212 | `test_agent_span_enabled` | ✅ PASSED | Span enabled |
| 213 | `test_tool_span_disabled_when_no_tracer` | ✅ PASSED | Tool span disabled |
| 214 | `test_record_resolution_noop_when_disabled` | ✅ PASSED | Noop when disabled |
| 215 | `test_record_resolution_enabled` | ✅ PASSED | Resolution recorded |
| 216 | `test_agent_service_map` | ✅ PASSED | All 6 agents mapped |

### TestDatadogMonitors (10 tests)
| # | Test | Status | What it tests |
|---|---|---|---|
| 217 | `test_queue_depth_monitor_has_query` | ✅ PASSED | Queue monitor query exists |
| 218 | `test_queue_depth_monitor_has_pagerduty` | ✅ PASSED | Queue monitor has PD tag |
| 219 | `test_error_rate_monitor_has_query` | ✅ PASSED | Error monitor query exists |
| 220 | `test_error_rate_monitor_has_pagerduty` | ✅ PASSED | Error monitor has PD tag |
| 221 | `test_latency_p95_monitor_has_query` | ✅ PASSED | Latency monitor query exists |
| 222 | `test_latency_p95_monitor_has_pagerduty` | ✅ PASSED | Latency monitor has PD tag |
| 223 | `test_get_all_monitors_returns_three` | ✅ PASSED | Returns 3 monitors |
| 224 | `test_validate_monitors_passes` | ✅ PASSED | Validation passes |
| 225 | `test_validate_monitors_fails_on_bad_query` | ✅ PASSED | Bad query caught |
| 226 | `test_export_monitors_is_valid_json` | ✅ PASSED | Export is valid JSON |

### TestCSATPipeline (11 tests)
| # | Test | Status | What it tests |
|---|---|---|---|
| 227 | `test_compute_csat_score_initial` | ✅ PASSED | Initial CSAT score |
| 228 | `test_compute_csat_score_multiple` | ✅ PASSED | CSAT after multiple events |
| 229 | `test_compute_csat_score_clamps_range` | ✅ PASSED | Score clamped to 0-1 |
| 230 | `test_compute_csat_score_with_agent` | ✅ PASSED | Per-agent breakdown |
| 231 | `test_ingest_resolution_event_basic` | ✅ PASSED | Event ingestion works |
| 232 | `test_ingest_resolution_event_sla` | ✅ PASSED | SLA enforcement (< 500ms) |
| 233 | `test_ingest_resolution_event_clamps_score` | ✅ PASSED | Score clamped on ingest |
| 234 | `test_get_rolling_csat_empty` | ✅ PASSED | Empty rolling window |
| 235 | `test_get_rolling_csat_after_events` | ✅ PASSED | Rolling window after events |
| 236 | `test_ingest_emits_datadog_metric` | ✅ PASSED | Datadog metric emitted |
| 237 | `test_sync_to_redis_no_url` | ✅ PASSED | Redis sync without URL |

---

## 7. `tests/test_tools.py` — 44 passed (M3)

### CRM Tools (11 tests)
| # | Test | Status | What it tests |
|---|---|---|---|
| 238 | `test_get_customer_profile_returns_expected_schema` | ✅ PASSED | Schema matches spec |
| 239 | `test_get_customer_profile_empty_customer_id` | ✅ PASSED | Empty ID → error |
| 240 | `test_get_customer_profile_whitespace_customer_id` | ✅ PASSED | Whitespace ID → error |
| 241 | `test_get_customer_profile_handles_unknown_customer` | ✅ PASSED | Unknown customer → error |
| 242 | `test_get_customer_profile_crm_timeout` | ✅ PASSED | CRM timeout → error |
| 243 | `test_get_customer_profile_connection_failure` | ✅ PASSED | Connection failure → error |
| 244 | `test_get_customer_profile_malformed_response` | ✅ PASSED | Bad JSON → error |
| 245 | `test_get_customer_profile_missing_base_url` | ✅ PASSED | Missing env var → error |
| 246 | `test_get_customer_profile_missing_api_key` | ✅ PASSED | Missing API key → error |
| 247 | `test_get_customer_profile_order_history_limited_to_10` | ✅ PASSED | Max 10 orders |
| 248 | `test_get_customer_profile_past_returns_limited_to_5` | ✅ PASSED | Max 5 returns |

### Payment Tools (16 tests)
| # | Test | Status | What it tests |
|---|---|---|---|
| 249 | `test_process_refund_stripe_success` | ✅ PASSED | Stripe refund works |
| 250 | `test_process_refund_paypal_success` | ✅ PASSED | PayPal refund works |
| 251 | `test_process_refund_unsupported_method` | ✅ PASSED | Unknown method → error |
| 252 | `test_process_refund_empty_order_id` | ✅ PASSED | Empty ID → error |
| 253 | `test_process_refund_invalid_amount` | ✅ PASSED | $0 amount → error |
| 254 | `test_process_refund_negative_amount` | ✅ PASSED | -$100 → error |
| 255 | `test_process_refund_missing_stripe_key` | ✅ PASSED | Missing Stripe key → error |
| 256 | `test_process_refund_missing_paypal_credentials` | ✅ PASSED | Missing PayPal creds → error |
| 257 | `test_process_refund_stripe_timeout` | ✅ PASSED | Stripe timeout → error |
| 258 | `test_process_refund_paypal_timeout` | ✅ PASSED | PayPal timeout → error |
| 259 | `test_process_refund_stripe_malformed_response` | ✅ PASSED | Bad Stripe JSON → error |
| 260 | `test_process_refund_paypal_malformed_response` | ✅ PASSED | Bad PayPal JSON → error |
| 261 | `test_process_refund_stripe_404` | ✅ PASSED | Stripe 404 → error |
| 262 | `test_process_refund_paypal_404` | ✅ PASSED | PayPal 404 → error |
| 263 | `test_process_refund_malformed_refund_cap` | ✅ PASSED | Bad cap env var |
| 264 | `test_process_refund_blocks_above_cap` | ✅ PASSED | $600 > $500 → blocked |

### Shipping Tools (10 tests)
| # | Test | Status | What it tests |
|---|---|---|---|
| 265 | `test_create_return_label_fedex_success` | ✅ PASSED | FedEx label works |
| 266 | `test_create_return_label_ups_success` | ✅ PASSED | UPS label works |
| 267 | `test_create_return_label_invalid_carrier` | ✅ PASSED | Unknown carrier → error |
| 268 | `test_create_return_label_empty_order_id` | ✅ PASSED | Empty ID → error |
| 269 | `test_create_return_label_missing_fedex_env` | ✅ PASSED | Missing FedEx env → error |
| 270 | `test_create_return_label_missing_ups_env` | ✅ PASSED | Missing UPS env → error |
| 271 | `test_create_return_label_fedex_timeout` | ✅ PASSED | FedEx timeout → error |
| 272 | `test_create_return_label_ups_timeout` | ✅ PASSED | UPS timeout → error |
| 273 | `test_create_return_label_fedex_malformed_response` | ✅ PASSED | Bad FedEx JSON → error |
| 274 | `test_create_return_label_ups_malformed_response` | ✅ PASSED | Bad UPS JSON → error |

### Replacement Order Tests (7 tests)
| # | Test | Status | What it tests |
|---|---|---|---|
| 275 | `test_create_replacement_order_success` | ✅ PASSED | OMS replacement works |
| 276 | `test_create_replacement_order_empty_order_id` | ✅ PASSED | Empty ID → error |
| 277 | `test_create_replacement_order_missing_base_url` | ✅ PASSED | Missing OMS URL → error |
| 278 | `test_create_replacement_order_missing_api_key` | ✅ PASSED | Missing API key → error |
| 279 | `test_create_replacement_order_404` | ✅ PASSED | OMS 404 → error |
| 280 | `test_create_replacement_order_timeout` | ✅ PASSED | OMS timeout → error |
| 281 | `test_create_replacement_order_malformed_response` | ✅ PASSED | Bad OMS JSON → error |

---

## 8. `tests/test_integration.py` — 40 passed (Lead)

### TestFixtureIntegrity (8 tests)
| # | Test | Status | What it tests |
|---|---|---|---|
| 282 | `test_orders_have_required_fields` | ✅ PASSED | orders.json has all fields |
| 283 | `test_customers_have_required_fields` | ✅ PASSED | customers.json has all fields |
| 284 | `test_messages_have_required_fields` | ✅ PASSED | messages.json has all fields |
| 285 | `test_resolutions_have_required_fields` | ✅ PASSED | resolutions.json has all fields |
| 286 | `test_all_customer_ids_in_orders_exist` | ✅ PASSED | Referential integrity |
| 287 | `test_all_message_customer_ids_exist` | ✅ PASSED | Message → customer link |
| 288 | `test_all_resolution_message_ids_exist` | ✅ PASSED | Resolution → message link |
| 289 | `test_intents_are_valid` | ✅ PASSED | All intents are known |

### TestCheckReturnPolicy (10 tests)
| # | Test | Status | What it tests |
|---|---|---|---|
| 290 | `test_eligible_within_window` | ✅ PASSED | Within 30-day window |
| 291 | `test_ineligible_outside_window` | ✅ PASSED | Outside window |
| 292 | `test_ineligible_excluded_category` | ✅ PASSED | Excluded category |
| 293 | `test_ineligible_fraud_flag` | ✅ PASSED | Fraud flag → escalate |
| 294 | `test_ineligible_final_sale` | ✅ PASSED | Final sale item |
| 295 | `test_eligible_mid_value_clean_account` | ✅ PASSED | Mid-value eligible |
| 296 | `test_unknown_order_returns_ineligible` | ✅ PASSED | Unknown order → error |
| 297 | `test_unknown_customer_returns_ineligible` | ✅ PASSED | Unknown customer → error |
| 298 | `test_eligible_high_value` | ✅ PASSED | High-value eligible |
| 299 | `test_return_schema_matches_spec` | ✅ PASSED | Schema matches spec |

### TestTrackingTools (9 tests)
| # | Test | Status | What it tests |
|---|---|---|---|
| 300 | `test_tracking_lookup_found` | ✅ PASSED | Found order returns tracking |
| 301 | `test_tracking_lookup_not_found` | ✅ PASSED | Missing order → error |
| 302 | `test_tracking_lookup_empty_order_id` | ✅ PASSED | Empty order_id → error |
| 303 | `test_tracking_lookup_output_contract` | ✅ PASSED | Output keys match spec |
| 304 | `test_faq_lookup_matches_keyword` | ✅ PASSED | Keyword match returns answer |
| 305 | `test_faq_lookup_no_match` | ✅ PASSED | No match → graceful |
| 306 | `test_faq_lookup_empty_query` | ✅ PASSED | Empty query → error |
| 307 | `test_faq_lookup_output_contract` | ✅ PASSED | Output keys match spec |
| 308 | `test_faq_lookup_multiple_keywords` | ✅ PASSED | Multi-word query |

### TestSessionHelpers (3 tests)
| # | Test | Status | What it tests |
|---|---|---|---|
| 309 | `test_session_structure_defaults` | ✅ PASSED | Session defaults |
| 310 | `test_agent_chain_appends` | ✅ PASSED | Agent chain append |
| 311 | `test_expected_agent_chains_from_resolutions` | ✅ PASSED | Resolution chains |

### TestIntentMapping (1 test)
| # | Test | Status | What it tests |
|---|---|---|---|
| 312 | `test_all_messages_mapped_to_known_route` | ✅ PASSED | All intents mapped |

### TestPipelineSkeletons (9 tests)
| # | Test | Status | What it tests |
|---|---|---|---|
| 313 | `test_return_request_routes_to_policy_agent` | ✅ PASSED | Return → PolicyAgent |
| 314 | `test_rejection_path_skips_resolution_agent` | ✅ PASSED | Rejection skips resolution |
| 315 | `test_legal_threat_routes_to_escalation_agent` | ✅ PASSED | Legal → EscalationAgent |
| 316 | `test_refund_cap_triggers_human_approval` | ✅ PASSED | Cap triggers approval |
| 317 | `test_fraud_flag_blocks_return_and_escalates` | ✅ PASSED | Fraud blocks + escalates |
| 318 | `test_pii_stripped_before_agent_receives_message` | ✅ PASSED | PII stripped |
| 319 | `test_excluded_category_rejects_automatically` | ✅ PASSED | Excluded → auto-reject |
| 320 | `test_session_persists_across_handoffs` | ✅ PASSED | Session persists |
| 321 | `test_full_return_pipeline_end_to_end` | ✅ PASSED | Full E2E pipeline |

---

## 9. `tests/test_tracking_tools.py` — 32 passed (Lead)

### TestTrackingLookupNominal (5 tests)
| # | Test | Status | What it tests |
|---|---|---|---|
| 322 | `test_delivered_order` | ✅ PASSED | Delivered order returns status |
| 323 | `test_in_transit_order` | ✅ PASSED | In-transit order |
| 324 | `test_processing_order` | ✅ PASSED | Processing order |
| 325 | `test_exception_order` | ✅ PASSED | Exception order |
| 326 | `test_order_not_in_tracking_data_but_in_repo` | ✅ PASSED | Fallback to repo |

### TestTrackingLookupErrors (4 tests)
| # | Test | Status | What it tests |
|---|---|---|---|
| 327 | `test_order_not_found` | ✅ PASSED | Missing order → error |
| 328 | `test_empty_order_id` | ✅ PASSED | Empty order_id → error |
| 329 | `test_whitespace_order_id` | ✅ PASSED | Whitespace → error |
| 330 | `test_none_like_order_id` | ✅ PASSED | None-like → error |

### TestTrackingLookupContract (5 tests)
| # | Test | Status | What it tests |
|---|---|---|---|
| 331 | `test_success_output_keys` | ✅ PASSED | All keys present |
| 332 | `test_error_output_keys` | ✅ PASSED | Error keys present |
| 333 | `test_success_field_is_bool` | ✅ PASSED | success is bool |
| 334 | `test_found_field_is_bool` | ✅ PASSED | found is bool |
| 335 | `test_idempotent` | ✅ PASSED | Same input → same output |

### TestFaqLookupNominal (9 tests)
| # | Test | Status | What it tests |
|---|---|---|---|
| 336 | `test_return_window_question` | ✅ PASSED | Return window FAQ |
| 337 | `test_refund_question` | ✅ PASSED | Refund FAQ |
| 338 | `test_shipping_question` | ✅ PASSED | Shipping FAQ |
| 339 | `test_tracking_question` | ✅ PASSED | Tracking FAQ |
| 340 | `test_damaged_item_question` | ✅ PASSED | Damaged item FAQ |
| 341 | `test_exchange_question` | ✅ PASSED | Exchange FAQ |
| 342 | `test_cancel_question` | ✅ PASSED | Cancel FAQ |
| 343 | `test_warranty_question` | ✅ PASSED | Warranty FAQ |
| 344 | `test_price_match_question` | ✅ PASSED | Price match FAQ |

### TestFaqLookupErrors (4 tests)
| # | Test | Status | What it tests |
|---|---|---|---|
| 345 | `test_no_match` | ✅ PASSED | No keyword match |
| 346 | `test_empty_query` | ✅ PASSED | Empty query → error |
| 347 | `test_whitespace_query` | ✅ PASSED | Whitespace → error |
| 348 | `test_unrelated_query` | ✅ PASSED | Unrelated query |

### TestFaqLookupContract (5 tests)
| # | Test | Status | What it tests |
|---|---|---|---|
| 349 | `test_success_output_keys` | ✅ PASSED | All keys present |
| 350 | `test_error_output_keys` | ✅ PASSED | Error keys present |
| 351 | `test_confidence_is_float` | ✅ PASSED | Confidence is float |
| 352 | `test_confidence_between_0_and_1` | ✅ PASSED | Confidence 0-1 |
| 353 | `test_idempotent` | ✅ PASSED | Same input → same output |

---

## Coverage Summary

| Area | Tests | Status |
|---|---|---|
| Policy Agent & Guardrails | 106 | ✅ Fully covered |
| Resolution Agent | 21 | ✅ Fully covered |
| Billing Agent | 18 | ✅ Fully covered |
| Communication & Escalation | 14 | ✅ Fully covered |
| Database Layer | 37 | ✅ Fully covered |
| Infrastructure & Observability | 41 | ✅ Fully covered |
| Tool Integrations | 44 | ✅ Fully covered |
| Integration & Pipeline | 40 | ✅ Fully covered |
| Tracking & FAQ Tools | 32 | ✅ Fully covered |
| **Total** | **353** | **0 skipped, 0 failed** |

---

*Generated by Lead on 2026-06-24. Run `pytest tests/ -v` to reproduce.*
