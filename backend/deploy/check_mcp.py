"""独立 MCP 客户端验收：使用与 AI 客户端相同的 stdio 配置真实发现并调用工具。"""

import argparse
import asyncio
import json
from contextlib import AsyncExitStack
from pathlib import Path
from typing import Any

import httpx2
from jsonschema import Draft202012Validator
from mcp import Client
from mcp.client.stdio import StdioServerParameters
from mcp.client.streamable_http import streamable_http_client

from tara_agent.mcp.transport import CATALOG_URI, META_KEY


async def check(config: Path, server: str, tool: str, arguments: dict[str, Any]) -> dict:
    entry = json.loads(config.read_text(encoding="utf-8"))["mcpServers"][server]
    async with AsyncExitStack() as stack:
        transport = "stdio"
        if "url" in entry:
            if not entry["url"].startswith("https://"):
                raise ValueError("Remote MCP requires HTTPS")
            transport = "streamable-http"
            http = await stack.enter_async_context(
                httpx2.AsyncClient(
                    headers=entry.get("headers", {}),
                    timeout=120,
                    trust_env=False,
                )
            )
            params = streamable_http_client(entry["url"], http_client=http)
        else:
            params = StdioServerParameters.model_validate(entry)
        client = await stack.enter_async_context(Client(params, read_timeout_seconds=120))
        listed = await client.list_tools()
        tools = {item.name: item for item in listed.tools}
        if tool not in tools:
            raise ValueError(f"Tool {tool!r} is unavailable. Available: {', '.join(sorted(tools))}")
        for item in tools.values():
            if (
                not item.description
                or not item.output_schema
                or not item.annotations.read_only_hint
            ):
                raise ValueError(f"Incomplete read-only tool contract: {item.name}")
            Draft202012Validator.check_schema(item.input_schema)
            Draft202012Validator.check_schema(item.output_schema)
        catalog = json.loads((await client.read_resource(CATALOG_URI)).contents[0].text)
        result = await client.call_tool(tool, arguments)
        if result.is_error or result.structured_content is None:
            raise ValueError(
                "; ".join(block.text for block in result.content if hasattr(block, "text"))
            )
        Draft202012Validator(tools[tool].output_schema).validate(result.structured_content)
        if result.meta[META_KEY]["catalog_uri"] != CATALOG_URI:
            raise ValueError("Missing source catalog reference")
        return {
            "status": "passed",
            "transport": transport,
            "server": server,
            "tools": sorted(tools),
            "tool_count": len(tools),
            "catalog": catalog,
            "call": {"name": tool, "arguments": arguments, "result": result.structured_content},
        }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True, help="Trusted mcpServers JSON file.")
    parser.add_argument("--server", default="tara")
    parser.add_argument("--tool", default="find_samples")
    parser.add_argument("--arguments", default='{"query":{"limit":1}}')
    parser.add_argument("--output", type=Path, help="Optional JSON acceptance report.")
    args = parser.parse_args()
    try:
        result = asyncio.run(check(args.config, args.server, args.tool, json.loads(args.arguments)))
    except Exception as error:
        # 子进程退出会经 anyio 形成异常组；将叶子原因给维护者，不淹没在栈信息中。
        def messages(item: BaseException) -> list[str]:
            if isinstance(item, BaseExceptionGroup):
                return [message for child in item.exceptions for message in messages(child)]
            return [str(item)]

        detail = "; ".join(dict.fromkeys(messages(error)))
        parser.exit(
            1, f"MCP acceptance failed: {detail}\nCheck startup stderr and client configuration.\n"
        )
    payload = json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    if args.output:
        args.output.write_text(payload, encoding="utf-8")
    print(payload, end="")


if __name__ == "__main__":
    main()
