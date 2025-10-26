import os
from pathlib import Path

import pytest


@pytest.fixture(autouse=True, scope="session")
def load_env() -> None:
    env_path = Path(__file__).resolve().parents[1] / ".env.example"
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            os.environ.setdefault(key, value)
