"""原始 reads 试点的只读结果查询契约。"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from tara_agent.domain.contracts import ResultMetadata


class ReadStudyQuery(BaseModel):
    model_config = ConfigDict(extra="forbid")
    job_id: str | None = Field(default=None, pattern=r"^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$")
    top_n: int = Field(default=20, ge=5, le=100)


class ReadStudyResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    query: ReadStudyQuery
    status: Literal["available_jobs", "completed"]
    items: list[dict] = Field(default_factory=list)
    observations: list[dict] = Field(default_factory=list)
    summary: dict = Field(default_factory=dict)
    metadata: ResultMetadata
