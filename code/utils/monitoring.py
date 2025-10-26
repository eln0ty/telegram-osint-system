import logging
import threading
import time
from collections import defaultdict
from typing import Dict


def setup_logging(level: str = "INFO") -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )


class StatsTracker:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._counters: Dict[str, int] = defaultdict(int)
        self._started_at = time.time()

    def increment(self, key: str, value: int = 1) -> None:
        with self._lock:
            self._counters[key] += value

    def get(self, key: str) -> int:
        with self._lock:
            return self._counters.get(key, 0)

    def snapshot(self) -> Dict[str, int]:
        with self._lock:
            return dict(self._counters)

    def uptime(self) -> float:
        return time.time() - self._started_at
