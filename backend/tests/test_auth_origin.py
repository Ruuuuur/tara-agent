import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from tara_agent.api.routes.auth import router
from tara_agent.auth import InvalidCredentialsError
from tara_agent.config import Settings


class RejectingLoginService:
    async def login(self, *, email: str, password: str):
        # 来源校验通过后才能进入认证；测试不连接数据库或创建账户。
        raise InvalidCredentialsError("测试凭据")


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("origin", "expected_status"),
    [
        ("http://localhost:3000", 401),
        ("http://127.0.0.1:3000", 401),
        ("http://localhost:3001", 403),
        ("http://127.0.0.1:3001", 403),
        ("https://untrusted.example", 403),
    ],
)
async def test_login_only_accepts_configured_frontend_origins(origin, expected_status):
    app = FastAPI()
    app.state.settings = Settings(_env_file=None)
    app.state.auth_service = RejectingLoginService()
    app.include_router(router, prefix="/api/v1")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/v1/auth/login",
            headers={"Origin": origin},
            json={"email": "test@example.com", "password": "test-password"},
        )
    assert response.status_code == expected_status
    if expected_status == 403:
        assert response.json()["detail"] == "请求来源不受信任。"
