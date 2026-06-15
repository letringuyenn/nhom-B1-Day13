from __future__ import annotations

import os

import pytest

# Unit and integration tests must not export telemetry to a real project.
os.environ["LANGFUSE_PUBLIC_KEY"] = ""
os.environ["LANGFUSE_SECRET_KEY"] = ""
os.environ["LANGFUSE_TRACING_ENABLED"] = "False"

from app import metrics
from app.incidents import STATE


@pytest.fixture(autouse=True)
def reset_runtime_state() -> None:
    metrics.reset()
    for incident in STATE:
        STATE[incident] = False
    yield
    metrics.reset()
    for incident in STATE:
        STATE[incident] = False
