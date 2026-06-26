"""
Kafka Message Ingestion
Owner: Member 5

Configures one consumer per inbound channel, each feeding into the
FastAPI webhook receiver. Runs as a standalone CLI process per pod
(matching k8s deployment.yaml).

Topics (set in .env):
    KAFKA_TOPIC_WEB_CHAT   — agent01.webchat
    KAFKA_TOPIC_EMAIL      — agent01.email
    KAFKA_TOPIC_WHATSAPP   — agent01.whatsapp
    KAFKA_TOPIC_SMS        — agent01.sms

Message schema (all topics):
    {
        "customer_id":  str,
        "channel":      str,
        "raw_message":  str,
        "timestamp":    str,   # ISO-8601
        "session_id":   str | None,
    }

Consumer group: one pod per channel type (matches k8s deployment.yaml).

Usage:
    python -m infra.kafka_config --channel web_chat
    python -m infra.kafka_config --channel email
    python -m infra.kafka_config --channel whatsapp
    python -m infra.kafka_config --channel sms

Environment variables required:
    KAFKA_BOOTSTRAP_SERVERS
    KAFKA_TOPIC_WEB_CHAT
    KAFKA_TOPIC_EMAIL
    KAFKA_TOPIC_WHATSAPP
    KAFKA_TOPIC_SMS
    WEBHOOK_URL  (default: http://localhost:8000/webhook/message)
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import signal
import sys
from datetime import datetime, timezone
from typing import Any

import httpx

logger = logging.getLogger("kafka_config")
logger.setLevel(logging.INFO)
_handler = logging.StreamHandler(sys.stdout)
_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
logger.addHandler(_handler)

_CHANNEL_TOPIC_ENV: dict[str, str] = {
    "web_chat": "KAFKA_TOPIC_WEB_CHAT",
    "email": "KAFKA_TOPIC_EMAIL",
    "whatsapp": "KAFKA_TOPIC_WHATSAPP",
    "sms": "KAFKA_TOPIC_SMS",
}

_VALID_CHANNELS = frozenset(_CHANNEL_TOPIC_ENV)

_RUNNING = True


def _shutdown_handler(signum: int, _frame: object) -> None:
    global _RUNNING
    logger.info("Received signal %s — shutting down consumer...", signum)
    _RUNNING = False


signal.signal(signal.SIGTERM, _shutdown_handler)
signal.signal(signal.SIGINT, _shutdown_handler)


def _resolve_topic(channel: str) -> str:
    """Resolve the Kafka topic name from environment for the given channel."""
    env_key = _CHANNEL_TOPIC_ENV[channel]
    topic = os.environ.get(env_key)
    if not topic:
        raise RuntimeError(f"{env_key} is not set — cannot start consumer for channel '{channel}'")
    return topic


def validate_message(msg: dict[str, Any]) -> list[str]:
    """Validate inbound message conforms to the schema contract.

    Returns a list of validation error messages (empty = valid).
    """
    errors: list[str] = []
    required = {"customer_id": str, "channel": str, "raw_message": str, "timestamp": str}
    for field, expected_type in required.items():
        value = msg.get(field)
        if value is None:
            errors.append(f"Missing required field: '{field}'")
        elif not isinstance(value, expected_type):
            errors.append(
                f"Field '{field}' must be {expected_type.__name__}, got {type(value).__name__}"
            )
    if (
        "session_id" in msg
        and msg["session_id"] is not None
        and not isinstance(msg["session_id"], str)
    ):
        errors.append("Field 'session_id' must be str | None")
    return errors


def build_message(
    customer_id: str,
    channel: str,
    raw_message: str,
    session_id: str | None = None,
) -> dict[str, Any]:
    """Build a Kafka message dict conforming to the schema contract."""
    return {
        "customer_id": customer_id,
        "channel": channel,
        "raw_message": raw_message,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "session_id": session_id,
    }


def create_consumer(channel: str) -> Any:
    """Create and return a KafkaConsumer for the given channel."""
    from kafka import KafkaConsumer

    topic = _resolve_topic(channel)
    group_id = f"agent01-{channel}-consumer"
    bootstrap = os.environ.get("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")

    logger.info(
        "Starting consumer — channel=%s, topic=%s, group=%s, bootstrap=%s",
        channel,
        topic,
        group_id,
        bootstrap,
    )
    return KafkaConsumer(
        topic,
        group_id=group_id,
        bootstrap_servers=bootstrap,
        value_deserializer=lambda b: json.loads(b.decode("utf-8")),
        auto_offset_reset="latest",
        enable_auto_commit=True,
        session_timeout_ms=30_000,
        heartbeat_interval_ms=10_000,
    )


def forward_message(payload: dict[str, Any], webhook_url: str) -> str | None:
    """POST a validated message to the FastAPI webhook.

    Returns error string on failure, None on success.
    """
    try:
        resp = httpx.post(webhook_url, json=payload, timeout=10.0)
        resp.raise_for_status()
        logger.info("Forwarded message — customer_id=%s", payload.get("customer_id"))
        return None
    except httpx.HTTPStatusError as exc:
        error = f"Webhook returned {exc.response.status_code}: {exc.response.text}"
        logger.error(error)
        return error
    except httpx.RequestError as exc:
        error = f"Webhook request failed: {exc}"
        logger.error(error)
        return error


def consume_loop(channel: str, webhook_url: str | None = None) -> int:
    """Run the consume-and-forward loop. Returns count of messages processed."""
    if webhook_url is None:
        webhook_url = os.environ.get("WEBHOOK_URL", "http://localhost:8000/webhook/message")

    consumer = create_consumer(channel)
    message_count = 0
    error_count = 0

    logger.info("Entering consume loop for channel='%s' — webhook=%s", channel, webhook_url)

    try:
        for raw_msg in consumer:
            if not _RUNNING:
                break

            val = raw_msg.value
            if not isinstance(val, dict):
                logger.warning("Non-dict message received — skipping")
                continue

            validation_errors = validate_message(val)
            if validation_errors:
                logger.warning("Invalid message: %s", "; ".join(validation_errors))
                error_count += 1
                continue

            err = forward_message(val, webhook_url)
            if err:
                error_count += 1
            else:
                message_count += 1

    except KeyboardInterrupt:
        logger.info("Interrupted — shutting down")
    finally:
        consumer.close()
        logger.info("Consumer closed — processed=%d, errors=%d", message_count, error_count)

    return message_count


def main() -> None:
    """CLI entry point: python -m infra.kafka_config --channel <name>."""
    parser = argparse.ArgumentParser(description="Kafka consumer per channel")
    parser.add_argument(
        "--channel",
        required=True,
        choices=sorted(_VALID_CHANNELS),
        help="Inbound channel to consume",
    )
    args = parser.parse_args()

    channel = args.channel
    try:
        consume_loop(channel)
    except RuntimeError as exc:
        logger.critical("Startup failed: %s", exc)
        sys.exit(1)
    except Exception:
        logger.critical("Unhandled exception in consume loop", exc_info=True)
        sys.exit(2)


if __name__ == "__main__":
    main()
