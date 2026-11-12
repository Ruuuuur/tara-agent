"""真实 HTTP 客户端验证认证、撤销、资源限制及独立科学结果。"""

import hashlib
import json
import os
import socket
import subprocess
import sys
import time

import anyio
import httpx
import httpx2
import pytest
from mcp import Client
from mcp.client.streamable_http import streamable_http_client
from starlette.responses import JSONResponse
from starlette.testclient import TestClient

from tara_agent.analysis import TaraComputeService
from tara_agent.analysis.compute_models import DiversityQuery
from tara_agent.mcp.http import AccessBoundary, HTTPSettings, build_app
from tara_agent.mcp.tokens import TokenRecord, TokenRegistry

from .test_mcp_external import processed as processed


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
def credentials(tmp_path):
    token = "fixture-" + "a" * 40
    path = tmp_path / "tokens.json"
    path.write_text(
        TokenRegistry(
            tokens=[
                TokenRecord(
                    client_id="test",
                    sha256=hashlib.sha256(token.encode()).hexdigest(),
                    expires_at=int(time.time()) + 3600,
                )
            ]
        ).model_dump_json()
    )
    return path, token


@pytest.fixture
def settings(processed, credentials):
    return HTTPSettings(
        public_url="https://testserver/mcp",
        token_file=credentials[0],
        processed_data_dir=processed.processed_dir,
    )


def test_auth_security_revocation(settings, credentials):
    path, token = credentials
    headers = {
        "Authorization": f"Bearer {token}",
        "accept": "application/json, text/event-stream",
        "mcp-protocol-version": "2025-11-25",
    }
    msg = {"jsonrpc": "2.0", "id": 1, "method": "tools/list"}
    with TestClient(build_app(settings)) as client:
        for method in ("GET", "POST", "DELETE"):
            assert client.request(method, "/mcp").status_code == 401
            response = client.request(method, "/mcp", headers={"Authorization": "Bearer wrong"})
            assert response.status_code == 401
        assert client.post("/mcp", json=msg, headers=headers).status_code == 200
        response = client.post("/mcp", json=msg, headers={**headers, "Origin": "https://evil.test"})
        assert response.status_code == 403
        response = client.post("/mcp", json=msg, headers={**headers, "Host": "evil.test"})
        assert response.status_code == 421
        response = client.post(
            "/mcp", content=b"x" * 70000, headers={**headers, "content-type": "application/json"}
        )
        assert response.status_code == 413
        records = json.loads(path.read_text())
        records["tokens"][0]["expires_at"] = 1
        path.write_text(json.dumps(records))
        assert client.post("/mcp", json=msg, headers=headers).status_code == 401
        path.write_text('{"tokens": []}')
        assert client.post("/mcp", json=msg, headers=headers).status_code == 401
        path.write_text("broken")
        response = client.post("/mcp", json=msg, headers=headers)
        assert response.status_code == 503 and token not in response.text


@pytest.mark.anyio
async def test_concurrency_and_rate(settings, credentials):
    entered, release = anyio.Event(), anyio.Event()

    async def slow(scope, receive, send):
        entered.set()
        await release.wait()
        await JSONResponse({"ok": True})(scope, receive, send)

    settings.max_concurrent = 1
    other = "b" * 32
    records = json.loads(credentials[0].read_text())
    records["tokens"].append(
        {
            "client_id": "other",
            "sha256": hashlib.sha256(other.encode()).hexdigest(),
            "expires_at": int(time.time()) + 3600,
        }
    )
    credentials[0].write_text(json.dumps(records))
    app = AccessBoundary(slow, settings)
    headers = {"Authorization": f"Bearer {credentials[1]}"}
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="https://testserver"
    ) as client:

        async def first():
            assert (await client.post("/mcp", headers=headers)).status_code == 200

        async with anyio.create_task_group() as group:
            group.start_soon(first)
            await entered.wait()
            response = await client.post("/mcp", headers=headers)
            assert response.status_code == 429 and response.json()["error"] == "server_busy"
            assert app.active == 1
            response = await client.post("/mcp", headers={"Authorization": f"Bearer {other}"})
            assert response.status_code == 429 and response.json()["error"] == "server_busy"
            release.set()
        assert app.active == 0
        app.windows["test"].extend([time.monotonic()] * settings.requests_per_minute)
        response = await client.post("/mcp", headers=headers)
        assert response.status_code == 429 and response.json()["error"] == "rate_limited"
        assert int(response.headers["retry-after"]) >= 1


@pytest.fixture
def http_server(settings):
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    env = {
        **os.environ,
        "TARA_MCP_PUBLIC_URL": str(settings.public_url),
        "TARA_MCP_TOKEN_FILE": str(settings.token_file),
        "TARA_MCP_PROCESSED_DATA_DIR": str(settings.processed_data_dir),
    }
    process = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "tara_agent.mcp.http:create_app",
            "--factory",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
            "--no-access-log",
        ],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    try:
        url = f"http://127.0.0.1:{port}"
        for _ in range(100):
            if process.poll() is not None:
                raise AssertionError(process.communicate()[1].decode())
            try:
                if httpx.get(url + "/healthz", timeout=1, trust_env=False).status_code == 200:
                    break
            except httpx.ConnectError:
                pass
            time.sleep(0.05)
        else:
            raise AssertionError("HTTP MCP did not start")
        yield url + "/mcp"
    finally:
        process.terminate()
        process.communicate(timeout=10)


@pytest.mark.anyio
@pytest.mark.parametrize("mode", ["auto", "legacy"])
async def test_http_discovery_parity_recovery(http_server, credentials, processed, mode):
    async with (
        httpx2.AsyncClient(
            headers={"Authorization": f"Bearer {credentials[1]}"}, timeout=30, trust_env=False
        ) as http,
        Client(streamable_http_client(http_server, http_client=http), mode=mode) as client,
    ):
        assert len((await client.list_tools()).tools) == 7
        catalog = json.loads((await client.read_resource("tara://data/catalog")).contents[0].text)
        assert catalog["core"]["generation"] == processed.manifest.generation
        bad = await client.call_tool("diversity_analysis", {"query": {"marker": "bad"}})
        assert bad.is_error
        for marker in ("v4", "v9"):
            query = DiversityQuery(marker=marker)
            expected = TaraComputeService(processed).diversity_analysis(query)
            result = await client.call_tool("diversity_analysis", {"query": {"marker": marker}})
            assert not result.is_error
            assert result.structured_content == expected.model_dump(mode="json")


def test_token_admin(tmp_path):
    registry, output = tmp_path / "registry.json", tmp_path / "secret"
    command = [sys.executable, "-m", "tara_agent.mcp.tokens", "--registry", str(registry)]
    result = subprocess.run(
        [*command, "create", "alice", "--output", str(output)],
        capture_output=True,
        text=True,
        check=True,
    )
    token = output.read_text().strip()
    assert token not in result.stdout and token not in registry.read_text()
    assert output.stat().st_mode & 0o777 == 0o600
    subprocess.run([*command, "revoke", "alice"], capture_output=True, check=True)
    assert json.loads(registry.read_text()) == {"tokens": []}
