-- Seed data for PostgreSQL — Agent 01 Return Processing System
-- Owner: Member 2

INSERT INTO customers (customer_id, fraud_flag, fraud_reason) VALUES
    ('CUST-001', FALSE, NULL),
    ('CUST-002', FALSE, NULL),
    ('CUST-003', FALSE, NULL),
    ('CUST-004', TRUE,  'chargeback_history'),
    ('CUST-005', FALSE, NULL)
ON CONFLICT (customer_id) DO NOTHING;

INSERT INTO orders (order_id, customer_id, item_category, days_since_purchase, price, damaged) VALUES
    ('ORD-001', 'CUST-001', 'electronics',   15,  199.99, FALSE),
    ('ORD-002', 'CUST-001', 'electronics',   45,  299.99, FALSE),
    ('ORD-003', 'CUST-002', 'digital_goods', 5,   49.99,  FALSE),
    ('ORD-004', 'CUST-003', 'clothing',      10,  89.99,  TRUE),
    ('ORD-005', 'CUST-004', 'home_goods',    20,  150.00, FALSE),
    ('ORD-006', 'CUST-005', 'electronics',   3,   799.99, FALSE)
ON CONFLICT (order_id) DO NOTHING;

INSERT INTO fraud_db_matches (customer_id, match_reason) VALUES
    ('CUST-005', 'suspicious_pattern_alpha')
ON CONFLICT (customer_id) DO NOTHING;
