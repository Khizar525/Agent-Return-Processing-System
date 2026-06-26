-- PostgreSQL Schema — Agent 01 Return Processing System
-- Owner: Member 2
-- Run:  psql -U postgres -d agent01_returns -f schema.sql

CREATE TABLE IF NOT EXISTS customers (
    customer_id     VARCHAR(20) PRIMARY KEY,
    fraud_flag      BOOLEAN NOT NULL DEFAULT FALSE,
    fraud_reason    VARCHAR(255),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS orders (
    order_id            VARCHAR(20) PRIMARY KEY,
    customer_id         VARCHAR(20) NOT NULL REFERENCES customers(customer_id),
    item_category       VARCHAR(50) NOT NULL,
    days_since_purchase INTEGER NOT NULL DEFAULT 0,
    price               DECIMAL(10,2) NOT NULL DEFAULT 0,
    damaged             BOOLEAN NOT NULL DEFAULT FALSE,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS fraud_db_matches (
    customer_id     VARCHAR(20) PRIMARY KEY REFERENCES customers(customer_id),
    match_reason    VARCHAR(255) NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_orders_customer ON orders(customer_id);
