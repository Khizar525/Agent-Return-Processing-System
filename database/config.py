"""
DB Config — connection settings from environment
"""

import os


DATABASE_URL: str = os.environ.get(
    "DATABASE_URL",
    "postgresql+asyncpg://postgres:postgres@localhost:5432/agent01_returns",
)

DB_ECHO: bool = os.environ.get("DB_ECHO", "0") == "1"

# When no real PostgreSQL, use file backend for dev
USE_FILE_BACKEND: bool = os.environ.get("USE_FILE_BACKEND", "1") == "1"
FILE_DB_PATH: str = os.environ.get(
    "FILE_DB_PATH",
    os.path.join(os.path.dirname(__file__), "data.json"),
)
