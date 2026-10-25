"""基于 DeepSeek 的问题规划与答案生成，提供可测试的接口。"""

from __future__ import annotations

import json
import logging
from collections.abc import AsyncIterator
from typing import Any, Protocol

from openai import AsyncOpenAI, OpenAIError
from pydantic import ValidationError

from tara_agent.agent.context import build_answer_model_input
from tara_agent.agent.conversation import conversation_context_payload
from tara_agent.agent.models import (
    AnalysisCapability,
    AnswerLanguage,
    ConversationContext,
    ModelStreamDelta,
    ModelUsage,
    RouteDecision,
    ToolDefinition,
    ToolPlan,
)
from tara_agent.agent.multistep import AnalysisDecision, WorkflowSelection, bounded_evidence
from tara_agent.agent.prompts import (
    ANSWER_SYSTEM_PROMPT,
    MULTI_STEP_SYSTEM_PROMPT,
    PLANNER_SYSTEM_PROMPT,
    ROUTER_SYSTEM_PROMPT,
    WORKFLOW_SELECTOR_SYSTEM_PROMPT,
)
from tara_agent.agent.resources import CAPABILITY_PROFILE
from tara_agent.config import Settings

# 最终汇总只解释已验证结果；关闭思考并保留较大的正文输出额度。
ANSWER_MAX_TOKENS = 65536


class AgentModelError(RuntimeError):
    """语言模型返回无法使用的回复时抛出。"""


class MultiToolPlanRequired(AgentModelError):
    """单步规划返回多个白名单调用，需要交由有界多步骤流程重新规划。"""

    def __init__(self, usage=None):
        super().__init__("该请求需要多步骤分析")
        self.usage = usage


class AgentModel(Protocol):
    @property
    def name(self) -> str: ...

    async def route(
        self,
        question: str,
        context: ConversationContext,
        tools: list[ToolDefinition],
    ) -> RouteDecision: ...

    async def plan(
        self,
        question: str,
        context: ConversationContext,
        tools: list[ToolDefinition],
    ) -> ToolPlan: ...

    def stream_answer(
        self,
        question: str,
        plan: ToolPlan,
        result: dict[str, Any],
        answer_language: AnswerLanguage = "zh",
    ) -> AsyncIterator[ModelStreamDelta]: ...


class DeepSeekChatModel:
    """使用 DeepSeek 兼容 OpenAI 的 Chat Completions API。"""

    def __init__(self, settings: Settings) -> None:
        if settings.deepseek_api_key is None:
            raise ValueError("DEEPSEEK_API_KEY is required")
        self._name = settings.deepseek_model
        self.reasoning_effort = settings.deepseek_reasoning_effort
        self.client = AsyncOpenAI(
            api_key=settings.deepseek_api_key.get_secret_value(),
            base_url=settings.deepseek_base_url,
            timeout=settings.deepseek_timeout_seconds,
        )

    @property
    def name(self) -> str:
        return self._name

    @property
    def provider(self) -> str:
        return "deepseek"

    @property
    def trace_parameters(self) -> dict[str, Any]:
        """返回不含密钥、可用于链路追踪的模型请求配置。"""

        return {
            "router": {
                "max_tokens": 1_000,
                "thinking": "disabled",
                "max_format_corrections": 1,
            },
            "planner": {
                "max_tokens": 1_200,
                "thinking": "disabled",
            },
            "workflow_selector": {"max_tokens": 2_000, "thinking": "disabled"},
            "multi_planner": {"max_tokens": 2_000, "thinking": "disabled"},
            "answer": {
                "max_tokens": ANSWER_MAX_TOKENS,
                "thinking": "disabled",
            },
        }

    async def route(
        self,
        question: str,
        context: ConversationContext,
        tools: list[ToolDefinition],
    ) -> RouteDecision:
        return await self._structured_decision(
            "route_request",
            RouteDecision,
            ROUTER_SYSTEM_PROMPT + _language_instruction(context.answer_language),
            {
                "question": question,
                "conversation_context": conversation_context_payload(context),
                "capability_profile": CAPABILITY_PROFILE,
                "available_tools": [
                    {"name": tool.name.value, "description": tool.description} for tool in tools
                ],
            },
            function=_route_function(
                [str(reference.trace_id) for reference in context.analysis_references]
            ),
            max_tokens=1_000,
            invalid_message="DeepSeek returned an invalid route decision",
            request_error_message="DeepSeek routing request failed",
        )

    async def plan(
        self,
        question: str,
        context: ConversationContext,
        tools: list[ToolDefinition],
    ) -> ToolPlan:
        function_tools = [
            {
                "type": "function",
                "function": {
                    "name": tool.name.value,
                    "description": tool.description,
                    "parameters": _schema_for_model(tool.input_schema),
                },
            }
            for tool in tools
        ]
        try:
            response = await self.client.chat.completions.create(
                model=self.name,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            PLANNER_SYSTEM_PROMPT + _language_instruction(context.answer_language)
                        ),
                    },
                    {
                        "role": "user",
                        "content": json.dumps(
                            {
                                "question": question,
                                "conversation_context": conversation_context_payload(context),
                            },
                            ensure_ascii=False,
                        ),
                    },
                ],
                tools=function_tools,
                tool_choice="required",
                max_tokens=1_200,
                extra_body={"thinking": {"type": "disabled"}},
            )
        except OpenAIError as exc:
            raise AgentModelError("DeepSeek planning request failed") from exc

        tool_calls = response.choices[0].message.tool_calls or []
        if len(tool_calls) > 1 and all(
            call.function.name in {tool.name.value for tool in tools} for call in tool_calls
        ):
            raise MultiToolPlanRequired(_model_usage(getattr(response, "usage", None)))
        if len(tool_calls) != 1:
            raise AgentModelError("模型未返回有效的分析工具，请重新提问。")
        tool_call = tool_calls[0]
        if tool_call.function.name not in {tool.name.value for tool in tools}:
            raise AgentModelError(
                f"当前数据服务未启用工具 {tool_call.function.name}，请检查服务器数据配置。"
            )
        try:
            arguments = json.loads(tool_call.function.arguments)
            return ToolPlan(
                tool_name=tool_call.function.name,
                arguments=arguments,
                rationale=f"问题需要调用 {tool_call.function.name}。",
                usage=_model_usage(getattr(response, "usage", None)),
            )
        except (TypeError, ValueError) as exc:
            raise AgentModelError("DeepSeek returned an invalid tool plan") from exc

    async def select_workflow(self, question, context, tools) -> WorkflowSelection:
        return await self._structured_decision(
            "select_analysis_workflow",
            WorkflowSelection,
            WORKFLOW_SELECTOR_SYSTEM_PROMPT + _language_instruction(context.answer_language),
            {
                "question": question,
                "context": conversation_context_payload(context),
                "tools": [tool.model_dump(mode="json") for tool in tools],
            },
        )

    async def next_analysis_step(self, question, context, tools, steps, budget) -> AnalysisDecision:
        return await self._structured_decision(
            "analysis_next_step",
            AnalysisDecision,
            MULTI_STEP_SYSTEM_PROMPT + _language_instruction(context.answer_language),
            {
                "question": question,
                "context": conversation_context_payload(context),
                "tools": [tool.model_dump(mode="json") for tool in tools],
                "verified_steps": bounded_evidence(steps),
                "remaining_budget": budget,
            },
        )

    async def _structured_decision(
        self,
        name,
        contract,
        prompt,
        payload,
        *,
        function=None,
        max_tokens=2000,
        invalid_message="模型返回了无效的分析决定",
        request_error_message="模型服务暂时不可用，请稍后重试。",
    ):
        if function is None:
            schema = contract.model_json_schema()
            schema["properties"].pop("usage", None)
            function = {
                "type": "function",
                "function": {
                    "name": name,
                    "description": prompt,
                    "parameters": _schema_for_model(schema),
                },
            }
        messages = [
            {"role": "system", "content": prompt},
            {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
        ]
        usages = []
        # 这里只纠正未执行工具的规划格式；接口错误和取消不额外重试。
        for attempt in range(2):
            try:
                response = await self.client.chat.completions.create(
                    model=self.name,
                    messages=messages,
                    tools=[function],
                    tool_choice="required",
                    max_tokens=max_tokens,
                    extra_body={"thinking": {"type": "disabled"}},
                )
            except OpenAIError as exc:
                logging.getLogger("uvicorn.error").warning(
                    "Decision API failed decision=%s failure=%s", name, type(exc).__name__
                )
                raise AgentModelError(request_error_message) from exc
            usages.append(_model_usage(getattr(response, "usage", None)))
            try:
                calls = response.choices[0].message.tool_calls or []
                if len(calls) != 1 or calls[0].function.name != name:
                    raise ValueError("single_function_call_required")
                decision = contract.model_validate(json.loads(calls[0].function.arguments))
            except (AttributeError, IndexError, TypeError, ValueError) as exc:
                # 不记录原始回答、参数或校验值，避免在日志中泄漏用户内容。
                feedback = _decision_validation_feedback(exc)
                logging.getLogger("uvicorn.error").warning(
                    "Decision validation failed decision=%s failure=%s issues=%s attempt=%d",
                    name,
                    type(exc).__name__,
                    ",".join(dict.fromkeys(item["type"] for item in feedback)),
                    attempt + 1,
                )
                if attempt == 1:
                    raise AgentModelError(invalid_message) from exc
                messages = [
                    *messages,
                    {
                        "role": "user",
                        "content": (
                            "The previous response failed structural validation "
                            f"({type(exc).__name__}). "
                            "Correct these validation errors: "
                            + json.dumps(feedback, ensure_ascii=False)
                            + ". "
                            f"Return exactly one {name} function call "
                            "with arguments matching its schema. "
                            "Use only the supplied context and verified evidence. "
                            "Do not invent tool results."
                        ),
                    },
                ]
                continue
            # 若某次用量未知，保持未知，不把剩余已知用量误报为完整总量。
            usage = None
            if all(item is not None for item in usages):
                usage = ModelUsage(
                    **{
                        field: sum(getattr(item, field) for item in usages)
                        if all(getattr(item, field) is not None for item in usages)
                        else None
                        for field in ModelUsage.model_fields
                    }
                )
            return decision.model_copy(update={"usage": usage})
        raise AssertionError("Unreachable structured decision state")

    async def stream_answer(
        self,
        question: str,
        plan: ToolPlan,
        result: dict[str, Any],
        answer_language: AnswerLanguage = "zh",
    ) -> AsyncIterator[ModelStreamDelta]:
        user_content = json.dumps(
            (
                {
                    "question": question,
                    "tool_result": {
                        **{k: v for k, v in result.items() if k != "analysis_steps"},
                        "analysis_steps": bounded_evidence(result["analysis_steps"]),
                    },
                }
                if "analysis_steps" in result
                else build_answer_model_input(question, plan.tool_name, result)
            ),
            ensure_ascii=False,
        )
        try:
            stream = await self.client.chat.completions.create(
                model=self.name,
                messages=[
                    {
                        "role": "system",
                        "content": _answer_system_prompt(answer_language),
                    },
                    {"role": "user", "content": user_content},
                ],
                max_tokens=ANSWER_MAX_TOKENS,
                stream=True,
                stream_options={"include_usage": True},
                extra_body={"thinking": {"type": "disabled"}},
            )
            received_content = False
            finish_reason = None
            async for chunk in stream:
                usage = _model_usage(getattr(chunk, "usage", None))
                if usage is not None:
                    yield ModelStreamDelta(kind="usage", usage=usage)
                if not chunk.choices:
                    continue
                finish_reason = getattr(chunk.choices[0], "finish_reason", None) or finish_reason
                delta = chunk.choices[0].delta
                reasoning = getattr(delta, "reasoning_content", None)
                if reasoning:
                    yield ModelStreamDelta(kind="reasoning", content=reasoning)
                content = delta.content
                if content:
                    received_content = True
                    yield ModelStreamDelta(kind="answer", content=content)
        except OpenAIError as exc:
            raise AgentModelError("DeepSeek answer request failed") from exc
        if finish_reason in {"length", "content_filter"}:
            raise AgentModelError(f"DeepSeek answer was incomplete ({finish_reason})")
        if not received_content:
            raise AgentModelError("DeepSeek returned an empty answer")


def _decision_validation_feedback(error: Exception) -> list[dict[str, str]]:
    """只回传字段位置与约束，不回显无效值、原始回答或异常堆栈。"""
    if isinstance(error, ValidationError):
        return [
            {
                "path": ".".join(map(str, item["loc"])) or "$",
                "type": item["type"],
                "message": item["msg"][:300],
            }
            for item in error.errors(include_input=False, include_context=False)[:5]
        ]
    if isinstance(error, json.JSONDecodeError):
        return [{"path": "$", "type": "json_invalid", "message": "Arguments must be valid JSON."}]
    return [
        {
            "path": "tool_calls",
            "type": "single_function_call_required",
            "message": "Return exactly one call to the requested function.",
        }
    ]


def _schema_for_model(value: Any) -> Any:
    """移除生成提示，同时保留 MCP 校验契约。"""

    if isinstance(value, dict):
        return {
            key: _schema_for_model(item)
            for key, item in value.items()
            if key not in {"default", "examples"}
        }
    if isinstance(value, list):
        return [_schema_for_model(item) for item in value]
    return value


def _route_function(analysis_reference_ids: list[str]) -> dict[str, Any]:
    reference_schema: dict[str, Any] = {
        "type": "array",
        "items": {"type": "string", "format": "uuid"},
        "description": "本次请求实际使用的已有分析 trace_id。",
    }
    if analysis_reference_ids:
        reference_schema["items"]["enum"] = analysis_reference_ids
    else:
        reference_schema["maxItems"] = 0

    return {
        "type": "function",
        "function": {
            "name": "route_request",
            "description": "判断当前用户请求应由 Tara Agent 如何处理。",
            "parameters": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "kind": {
                        "type": "string",
                        "enum": [
                            "direct_answer",
                            "analysis",
                            "clarify",
                            "unsupported",
                        ],
                    },
                    "rationale": {"type": "string", "minLength": 1, "maxLength": 300},
                    "response": {"type": "string", "maxLength": 2_000},
                    "capability_requirements": {
                        "type": "array",
                        "items": {
                            "type": "string",
                            "enum": [capability.value for capability in AnalysisCapability],
                        },
                        "maxItems": 10,
                    },
                    "analysis_reference_ids": reference_schema,
                },
                "required": [
                    "kind",
                    "rationale",
                    "response",
                    "capability_requirements",
                    "analysis_reference_ids",
                ],
            },
        },
    }


def _model_usage(value: Any) -> ModelUsage | None:
    """把兼容 OpenAI 的用量对象转换为稳定的内部结构。"""

    if value is None:
        return None
    prompt_details = getattr(value, "prompt_tokens_details", None)
    completion_details = getattr(value, "completion_tokens_details", None)
    return ModelUsage(
        input_tokens=value.prompt_tokens,
        output_tokens=value.completion_tokens,
        total_tokens=value.total_tokens,
        cached_tokens=getattr(prompt_details, "cached_tokens", None),
        reasoning_tokens=getattr(completion_details, "reasoning_tokens", None),
    )


def _answer_system_prompt(language: AnswerLanguage) -> str:
    """界面名称按回答语言提供，避免模型照抄中文提示中的按钮名。"""

    label = "More results" if language == "en" else "选择更多结果"
    prompt = ANSWER_SYSTEM_PROMPT.replace("“选择更多结果”", f"“{label}”")
    return prompt + _language_instruction(language)


def _language_instruction(language: AnswerLanguage) -> str:
    """本轮语言选择优先于基础提示及历史消息中的语言。"""

    name = "English" if language == "en" else "简体中文"
    return (
        f"\n本轮语言要求（优先于上述语言约定）：所有面向用户的 response、rationale 和最终回答"
        f"必须使用{name}，即使问题或历史消息使用其他语言。"
        "保留工具名、字段名、样本标识、数据集名、单位和科学数值原文。"
    )
