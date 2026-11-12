"""独立客户端共用的 MCP 边界：保留科学结果，补充可纠正错误与来源入口。"""

import logging
from typing import Any

from mcp.server import MCPServer
from mcp.server.mcpserver.context import Context
from mcp.server.mcpserver.exceptions import ToolError, UnexpectedToolError
from mcp.types import CallToolResult, TextContent, Tool
from pydantic import ValidationError

from tara_agent.analysis.service import AnalysisNotFoundError

logger = logging.getLogger(__name__)
CATALOG_URI = "tara://data/catalog"
META_KEY = "org.tara-agent/context"


class TaraMCPServer(MCPServer):
    """只增加传输层约束，不改写分析函数或科学返回 Schema。"""

    def __init__(self, *, data_context: dict[str, Any], **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.data_context = data_context

    async def list_tools(self) -> list[Tool]:
        tools = await super().list_tools()
        for tool in tools:
            # SDK 的外层函数参数模型默认忽略额外字段；声明与执行都须禁止。
            tool.input_schema["additionalProperties"] = False
        return tools

    async def call_tool(
        self, name: str, arguments: dict[str, Any], context: Context | None = None
    ) -> CallToolResult:
        tools = {tool.name: tool for tool in await self.list_tools()}
        if name not in tools:
            return self._failure(name, "unknown_tool", "Unknown tool; use tools/list first.")
        extra = sorted(arguments.keys() - tools[name].input_schema["properties"].keys())
        if extra:
            return self._failure(
                name,
                "invalid_arguments",
                "Unexpected top-level arguments.",
                [{"field": key, "type": "extra_forbidden"} for key in extra],
            )
        try:
            result = await super().call_tool(name, arguments, context)
        except ToolError as error:
            # 原始异常链保留 SDK 参数校验与领域异常的区别，不依赖错误文本猜测。
            causes: list[BaseException] = []
            current: BaseException | None = error
            while current is not None:
                causes.append(current)
                current = current.__cause__
            validation = next((e for e in causes if isinstance(e, ValidationError)), None)
            if isinstance(error, UnexpectedToolError):
                logger.exception("MCP tool %r failed unexpectedly", name)
                return self._failure(
                    name, "internal_error", "Analysis failed; contact the maintainer."
                )
            if validation is not None:
                fields = [
                    {
                        "field": ".".join(map(str, item["loc"])),
                        "type": item["type"],
                        "message": item["msg"],
                    }
                    for item in validation.errors(include_input=False, include_context=False)
                ]
                return self._failure(
                    name, "invalid_arguments", "Arguments do not match the tool schema.", fields
                )
            code = (
                "not_found"
                if any(isinstance(e, AnalysisNotFoundError) for e in causes)
                else "analysis_error"
            )
            return self._failure(name, code, str(error))
        # structuredContent 与直接调用分析服务完全一致，版本入口放在协议 _meta 中。
        result.meta = {**(result.meta or {}), META_KEY: self._context(name)}
        return result

    def _context(self, name: str) -> dict[str, Any]:
        return {
            "contract_version": 1,
            "tool": name,
            "catalog_uri": CATALOG_URI,
            "configured_data": self.data_context,
        }

    def _failure(
        self, name: str, code: str, message: str, fields: list[dict[str, str]] | None = None
    ) -> CallToolResult:
        error = {"code": code, "message": message, "fields": fields or []}
        return CallToolResult(
            content=[
                TextContent(
                    type="text",
                    text=f"{code}: {message}"
                    + (
                        " "
                        + "; ".join(f"{f['field']}: {f.get('message', f['type'])}" for f in fields)
                        if fields
                        else ""
                    ),
                )
            ],
            is_error=True,
            _meta={META_KEY: {**self._context(name), "error": error}},
        )
