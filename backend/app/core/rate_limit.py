from __future__ import annotations

import hashlib
import logging
import time
from collections import defaultdict, deque
from threading import Lock
from uuid import uuid4

from fastapi import HTTPException, Request, status
from redis import Redis

from app.core.config import settings

logger = logging.getLogger(__name__)

_hits: dict[tuple[str, str], deque[float]] = defaultdict(deque)
_hits_lock = Lock()

_redis_conn: Redis | None = None
_redis_lock = Lock()
_redis_warned = False

_REDIS_SLIDING_WINDOW_LUA = """
local key = KEYS[1]
local now_ms = tonumber(ARGV[1])
local window_ms = tonumber(ARGV[2])
local max_requests = tonumber(ARGV[3])
local member = ARGV[4]

redis.call('ZREMRANGEBYSCORE', key, '-inf', now_ms - window_ms)
local count = redis.call('ZCARD', key)
if count >= max_requests then
  local oldest = redis.call('ZRANGE', key, 0, 0, 'WITHSCORES')
  local retry_after = 1
  if oldest[2] then
    local remain_ms = window_ms - (now_ms - tonumber(oldest[2]))
    if remain_ms > 0 then
      retry_after = math.ceil(remain_ms / 1000)
    end
  end
  return {0, retry_after}
end

redis.call('ZADD', key, now_ms, member)
redis.call('EXPIRE', key, math.ceil(window_ms / 1000) + 1)
return {1, 0}
"""


def _get_client_ip(request: Request) -> str:
    if bool(getattr(settings, "RATE_LIMIT_TRUST_PROXY_HEADERS", False)):
        forwarded_for = (request.headers.get("x-forwarded-for") or "").strip()
        if forwarded_for:
            return forwarded_for.split(",")[0].strip() or "unknown"
    if request.client and request.client.host:
        return request.client.host
    return "unknown"


def _route_key(request: Request) -> str:
    route = request.scope.get("route")
    route_path = getattr(route, "path", None)
    if isinstance(route_path, str) and route_path:
        return route_path
    return request.url.path or "unknown"


def _token_fingerprint(request: Request) -> str | None:
    raw_token = (
        request.headers.get("X-API-Token")
        or request.headers.get("x-api-token")
        or request.query_params.get("api_token")
        or ""
    ).strip()
    if not raw_token:
        return None
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()[:12]


def _rate_limit_identity(request: Request) -> str:
    token_fp = _token_fingerprint(request)
    principal = f"token:{token_fp}" if token_fp else f"ip:{_get_client_ip(request)}"
    return f"{principal}|route:{_route_key(request)}"


def _raise_rate_limit(bucket: str, retry_after: int) -> None:
    raise HTTPException(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        detail=f"Rate limit exceeded ({bucket}), retry in {retry_after}s",
        headers={"Retry-After": str(retry_after)},
    )


def _enforce_rate_limit_memory(
    request: Request,
    bucket: str,
    *,
    max_requests: int,
    window_sec: int,
) -> None:
    now = time.monotonic()
    key = (bucket, _rate_limit_identity(request))

    with _hits_lock:
        timestamps = _hits[key]
        cutoff = now - window_sec
        while timestamps and timestamps[0] < cutoff:
            timestamps.popleft()

        if len(timestamps) >= max_requests:
            retry_after = max(1, int(window_sec - (now - timestamps[0])))
            _raise_rate_limit(bucket, retry_after)

        timestamps.append(now)


def _get_redis_conn() -> Redis:
    global _redis_conn
    if _redis_conn is not None:
        return _redis_conn
    with _redis_lock:
        if _redis_conn is not None:
            return _redis_conn
        conn = Redis.from_url(
            settings.REDIS_URL,
            socket_connect_timeout=1.5,
            socket_timeout=2.0,
            health_check_interval=30,
        )
        conn.ping()
        _redis_conn = conn
    return _redis_conn


def _enforce_rate_limit_redis(
    request: Request,
    bucket: str,
    *,
    max_requests: int,
    window_sec: int,
) -> None:
    identity = _rate_limit_identity(request)
    conn = _get_redis_conn()
    key = f"rl:{bucket}:{identity}"
    now_ms = int(time.time() * 1000)
    member = f"{now_ms}:{uuid4().hex[:8]}"
    allowed, retry_after = conn.eval(
        _REDIS_SLIDING_WINDOW_LUA,
        1,
        key,
        now_ms,
        int(window_sec * 1000),
        max_requests,
        member,
    )
    if int(allowed) != 1:
        _raise_rate_limit(bucket, max(1, int(retry_after)))


def enforce_rate_limit(
    request: Request,
    bucket: str,
    *,
    max_requests: int,
    window_sec: int,
) -> None:
    """
    速率限制：
    - 支持 Redis 共享桶（多实例一致）；
    - Redis 不可用时自动降级到内存桶，保证可用性优先。
    - 计数维度：bucket + (token 或 IP) + 路由。
    """
    global _redis_warned
    if not settings.RATE_LIMIT_ENABLED:
        return

    if max_requests <= 0 or window_sec <= 0:
        return

    backend = (getattr(settings, "RATE_LIMIT_BACKEND", "memory") or "memory").lower()
    if backend == "redis":
        try:
            _enforce_rate_limit_redis(
                request,
                bucket,
                max_requests=max_requests,
                window_sec=window_sec,
            )
            return
        except HTTPException:
            raise
        except Exception as exc:
            if not _redis_warned:
                logger.warning("rate limit redis backend unavailable, fallback to memory: %s", exc)
                _redis_warned = True
    _enforce_rate_limit_memory(
        request,
        bucket,
        max_requests=max_requests,
        window_sec=window_sec,
    )
