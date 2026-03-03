from __future__ import annotations

import json
import logging
from collections import defaultdict
from threading import Lock
from typing import Any

_counter_lock = Lock()
_counters: dict[str, int] = defaultdict(int)


def increment_counter(name: str, value: int = 1) -> int:
    with _counter_lock:
        _counters[name] += value
        return _counters[name]


def get_counters_snapshot() -> dict[str, int]:
    with _counter_lock:
        return dict(_counters)


def log_event(
    logger: logging.Logger,
    level: int,
    event_name: str,
    **fields: Any,
) -> None:
    payload = {"event": event_name, **fields}
    logger.log(level, "%s", json.dumps(payload, ensure_ascii=False, default=str))
