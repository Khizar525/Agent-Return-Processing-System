"""
Redis Session Store
Owner: Project Lead

Manages the Session object lifecycle for all active conversations.
Every agent handoff reads and writes through this module —
no agent accesses Redis directly.

Session schema:
    {
        "customer_id":       str,
        "channel":           str,
        "intent":            str | None,
        "policy_decision":   dict | None,
        "resolution_action": str | None,
        "agent_chain":       list[str],
        "timestamps": {
            "created_at":    str,   # ISO-8601
            "updated_at":    str,
            "resolved_at":   str | None,
        },
        "last_output":       str | None,
    }

TTL policy:
    Active sessions:  REDIS_SESSION_TTL_SECONDS  (default 86400  = 24 hours)
    Archive:          REDIS_ARCHIVE_TTL_SECONDS   (default 7776000 = 90 days)
"""

import json
import os
import uuid
from datetime import datetime, timezone

import redis.asyncio as aioredis

_redis: aioredis.Redis | None = None


def _get_client() -> aioredis.Redis:
    global _redis
    if _redis is None:
        _redis = aioredis.from_url(
            os.environ.get("REDIS_URL", "redis://localhost:6379"),
            decode_responses=True,
        )
    return _redis


SESSION_TTL = int(os.environ.get("REDIS_SESSION_TTL_SECONDS", 86400))
ARCHIVE_TTL = int(os.environ.get("REDIS_ARCHIVE_TTL_SECONDS", 7_776_000))


async def get_session(session_id: str) -> dict:
    """Load session from Redis. Returns empty dict if not found."""
    client = _get_client()
    raw = await client.get(f"session:{session_id}")
    return json.loads(raw) if raw else {}


async def save_session(session: dict, existing_id: str | None = None) -> str:
    """
    Persist session to Redis and return the session_id.
    Creates a new session_id if none provided.
    """
    client = _get_client()
    session_id = existing_id or str(uuid.uuid4())

    now = datetime.now(timezone.utc).isoformat()
    session.setdefault("timestamps", {"created_at": now, "updated_at": now, "resolved_at": None})
    session["timestamps"]["updated_at"] = now

    await client.setex(
        f"session:{session_id}",
        SESSION_TTL,
        json.dumps(session),
    )
    return session_id


async def archive_session(session_id: str) -> None:
    """Move a resolved session to the long-term archive key with extended TTL."""
    client = _get_client()
    raw = await client.get(f"session:{session_id}")
    if raw:
        await client.setex(f"archive:{session_id}", ARCHIVE_TTL, raw)
        await client.delete(f"session:{session_id}")


async def close() -> None:
    """Gracefully close the Redis connection (call on app shutdown)."""
    global _redis
    if _redis:
        await _redis.aclose()
        _redis = None
