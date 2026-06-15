from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")

DEFAULT_BASE_URL = os.getenv(
    "LAB_BASE_URL",
    os.getenv("BASE_URL", "http://127.0.0.1:8013"),
).rstrip("/")


def normalize_base_url(value: str) -> str:
    return value.strip().rstrip("/")
