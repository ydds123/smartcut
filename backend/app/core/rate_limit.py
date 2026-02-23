from collections import defaultdict, deque
from threading import Lock
import time

from fastapi import HTTPException, Request, status

from app.core.config import settings

_hits: dict[tuple[str, str], deque[float]] = defaultdict(deque)
_hits_lock = Lock()


def _get_client_ip(request: Request) -> str:
    forwarded_for = (request.headers.get("x-forwarded-for") or "").strip()
    if forwarded_for:
        return forwarded_for.split(",")[0].strip() or "unknown"
    if request.client and request.client.host:
        return request.client.host
    return "unknown"


def enforce_rate_limit(
    request: Request,
    bucket: str,
    *,
    max_requests: int,
    window_sec: int,
) -> None:
    """
    轻量级内存限流（单进程）：
    - 按 bucket + client_ip 计数
    - 超出窗口内最大请求数时返回 429
    """
    if not settings.RATE_LIMIT_ENABLED:
        return

    if max_requests <= 0 or window_sec <= 0:
        return

    now = time.monotonic()
    key = (bucket, _get_client_ip(request))

    with _hits_lock:
        timestamps = _hits[key]
        cutoff = now - window_sec
        while timestamps and timestamps[0] < cutoff:
            timestamps.popleft()

        if len(timestamps) >= max_requests:
            retry_after = max(1, int(window_sec - (now - timestamps[0])))
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Rate limit exceeded ({bucket}), retry in {retry_after}s",
                headers={"Retry-After": str(retry_after)},
            )

        timestamps.append(now)
