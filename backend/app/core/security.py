import secrets

from fastapi import Header, HTTPException, Query, status

from app.core.config import settings


def require_api_token(
    x_api_token: str | None = Header(default=None, alias="X-API-Token"),
    api_token: str | None = Query(default=None),
) -> None:
    """
    可开关 API Token 认证：
    - 关闭时不做任何校验（开发默认）；
    - 开启时支持 Header 或 Query 传入 token（兼容 SSE/静态资源）。
    """
    if not settings.API_AUTH_ENABLED:
        return

    expected = (settings.API_AUTH_TOKEN or "").strip()
    if not expected:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="API auth enabled but API_AUTH_TOKEN is not configured",
        )

    provided = (x_api_token or api_token or "").strip()
    if not provided or not secrets.compare_digest(provided, expected):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unauthorized",
            headers={"WWW-Authenticate": "Bearer"},
        )
