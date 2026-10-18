"""启动前有界预热；只读常用路径，不调用模型或创建产品记录。"""

import asyncio
import logging
import time
from uuid import uuid4

from fastapi import FastAPI

from tara_agent.agent.models import ToolName
from tara_agent.domain.contracts import Marker

# 使用现有服务器日志处理器，确保启动成功日志在生产默认日志级别下可见。
logger = logging.getLogger("uvicorn.error")


async def warm_up(application: FastAPI) -> None:
    settings = application.state.settings
    if not settings.startup_warmup_enabled:
        application.state.startup_warmup_status = "disabled"
        return

    application.state.startup_warmup_status = "running"
    started = time.monotonic()
    steps: list[str] = []
    try:
        async with asyncio.timeout(settings.startup_warmup_timeout_seconds):
            database = application.state.database
            if database is not None:
                await database.warm_up(connections=min(4, settings.database_pool_size))
                await application.state.auth_service.authenticate("tara-startup-readonly-warmup")
                await application.state.run_repository.list_sessions(
                    user_id=str(uuid4()),
                    limit=1,
                    offset=0,
                )
                steps.append("database_auth_history")

            gateway = application.state.tool_gateway
            if gateway is not None:
                await gateway.call(ToolName.FIND_SAMPLES, {"query": {"limit": 2}})
                steps.append("sample_query")
                reader = application.state.data_reader
                if reader is not None:
                    for marker in (Marker.V4, Marker.V9):
                        sample_ids = reader.marker_sample_ids(marker)[:2]
                        if sample_ids:
                            await gateway.call(
                                ToolName.DIVERSITY_ANALYSIS,
                                {
                                    "query": {
                                        "marker": marker.value,
                                        "sample_ids": sample_ids,
                                        "limit": 2,
                                    }
                                },
                            )
                            steps.append(f"{marker.value}_bounded_diversity")

            suggestions = application.state.question_suggestions
            if suggestions is not None:
                await suggestions.get_batch(limit=1)
                steps.append("suggestions")
        application.state.startup_warmup_status = "completed"
        logger.info(
            "Startup warmup completed seconds=%.3f steps=%s", time.monotonic() - started, steps
        )
    except Exception as error:
        # 预热不是业务前置条件；超时或可选路径失败时仍启动服务，且不记录潜在凭据。
        application.state.startup_warmup_status = "failed"
        logger.warning(
            "Startup warmup failed seconds=%.3f error_type=%s completed_steps=%s",
            time.monotonic() - started,
            type(error).__name__,
            steps,
        )
