"""
Kafka Message Ingestion
Owner: Member 5

Configures one consumer per inbound channel, each feeding into the
FastAPI webhook receiver.

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

Environment variables required:
    KAFKA_BOOTSTRAP_SERVERS
    KAFKA_TOPIC_WEB_CHAT
    KAFKA_TOPIC_EMAIL
    KAFKA_TOPIC_WHATSAPP
    KAFKA_TOPIC_SMS
"""

# TODO (Member 5): implement Kafka consumers below
