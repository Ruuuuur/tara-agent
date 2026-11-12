"""可独立部署的标准 MCP Streamable HTTP 入口，不加载网站数据库或模型密钥。"""

import hashlib
import hmac
import math
import time
from collections import deque
from pathlib import Path
from typing import Literal

from mcp.server.transport_security import TransportSecuritySettings
from pydantic import Field, HttpUrl
from pydantic_settings import BaseSettings, SettingsConfigDict
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from tara_agent.data.matou_reader import MatouDataReader
from tara_agent.data.reader import ProcessedDataReader
from tara_agent.mcp.server import create_server
from tara_agent.mcp.tokens import load_registry


class HTTPSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="TARA_MCP_", extra="ignore")
    public_url: HttpUrl
    auth_mode: Literal["bearer", "none"] = "bearer"
    token_file: Path | None = None
    processed_data_dir: Path
    matou_data_dir: Path | None = None
    max_concurrent: int = Field(default=2, ge=1, le=8)
    requests_per_minute: int = Field(default=60, ge=10, le=600)
    max_request_bytes: int = Field(default=65536, ge=1024, le=1048576)


class AccessBoundary:
    """单进程有界入口：支持令牌或匿名访问，忙时立即拒绝，不排队积累任务。"""

    def __init__(self, app: ASGIApp, settings: HTTPSettings):
        self.app = app
        self.settings = settings
        self.active = 0
        self.active_clients: set[str] = set()
        self.windows: dict[str, deque[float]] = {}
        if settings.auth_mode == "bearer":
            if settings.token_file is None:
                raise ValueError("Bearer authentication requires TARA_MCP_TOKEN_FILE")
            load_registry(settings.token_file)  # 认证启用时必须有有效注册表。

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        if scope["path"] == "/healthz" and scope["method"] == "GET":
            await JSONResponse({"status": "ok"})(scope, receive, send)
            return
        if scope["path"] != "/mcp":
            await JSONResponse({"error": "not_found"}, status_code=404)(scope, receive, send)
            return
        if self.settings.auth_mode == "none":
            identity = "anonymous"
            valid_ids = {identity}
        else:
            headers = {k.lower(): v for k, v in scope["headers"]}
            authorization = headers.get(b"authorization", b"").decode("latin-1")
            scheme, _, token = authorization.partition(" ")
            identity = None
            try:
                registry = load_registry(self.settings.token_file)
                if scheme.lower() == "bearer" and 20 <= len(token) <= 256:
                    digest = hashlib.sha256(token.encode()).hexdigest()
                    for item in registry.tokens:
                        if (
                            hmac.compare_digest(item.sha256, digest)
                            and item.expires_at > time.time()
                        ):
                            identity = item.client_id
            except (OSError, ValueError):
                await JSONResponse({"error": "authentication_unavailable"}, status_code=503)(
                    scope, receive, send
                )
                return
            if identity is None:
                await JSONResponse(
                    {"error": "invalid_token"},
                    status_code=401,
                    headers={
                        "WWW-Authenticate": 'Bearer realm="tara-mcp"',
                        "Cache-Control": "no-store",
                    },
                )(scope, receive, send)
                return
            valid_ids = {item.client_id for item in registry.tokens}
        # 匿名访问共用一个速率窗口；令牌模式只保留有效注册身份的窗口。
        self.windows = {k: v for k, v in self.windows.items() if k in valid_ids}
        window = self.windows.setdefault(identity, deque())
        now = time.monotonic()
        while window and window[0] <= now - 60:
            window.popleft()
        if len(window) >= self.settings.requests_per_minute:
            await self._busy(scope, receive, send, "rate_limited", math.ceil(60 - now + window[0]))
            return
        window.append(now)
        # 本入口只返回无状态 JSON，不开放无用途的常驻 GET/SSE 连接。
        if scope["method"] != "POST":
            await JSONResponse(
                {"error": "method_not_allowed"}, status_code=405, headers={"Allow": "POST"}
            )(scope, receive, send)
            return
        limited = True
        if limited and (
            self.active >= self.settings.max_concurrent
            or (self.settings.auth_mode == "bearer" and identity in self.active_clients)
        ):
            await self._busy(scope, receive, send, "server_busy", 3)
            return
        if limited:
            self.active += 1
            self.active_clients.add(identity)
        try:
            # SDK 的同步工具在 anyio 工作线程中执行且取消被屏蔽，直到计算结束才释放槽。
            await self.app(scope, receive, send)
        finally:
            if limited:
                self.active -= 1
                self.active_clients.discard(identity)

    @staticmethod
    async def _busy(scope: Scope, receive: Receive, send: Send, error: str, retry: int) -> None:
        await JSONResponse(
            {"error": error, "retryable": True},
            status_code=429,
            headers={"Retry-After": str(max(1, retry))},
        )(scope, receive, send)


def build_app(settings: HTTPSettings, reader: ProcessedDataReader | None = None) -> AccessBoundary:
    url = settings.public_url
    if (
        url.scheme != "https"
        or url.path != "/mcp"
        or url.query
        or url.fragment
        or url.username
        or url.password
    ):
        raise ValueError("TARA_MCP_PUBLIC_URL must be an HTTPS URL ending in /mcp")
    reader = reader or ProcessedDataReader(settings.processed_data_dir)
    matou = MatouDataReader(settings.matou_data_dir) if settings.matou_data_dir else None
    server = create_server(reader, matou_reader=matou)
    origin = f"{url.scheme}://{url.host}" + (f":{url.port}" if url.port != 443 else "")
    host = url.host + (f":{url.port}" if url.port != 443 else "")
    app = server.streamable_http_app(
        streamable_http_path="/mcp",
        stateless_http=True,
        json_response=True,
        max_request_body_size=settings.max_request_bytes,
        transport_security=TransportSecuritySettings(
            enable_dns_rebinding_protection=True,
            allowed_hosts=[host, f"{url.host}:443", "127.0.0.1:*", "localhost:*"],
            allowed_origins=[origin],
        ),
    )
    return AccessBoundary(app, settings)


def create_app() -> AccessBoundary:
    return build_app(HTTPSettings())
