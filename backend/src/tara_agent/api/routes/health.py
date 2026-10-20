"""存活状态与就绪状态接口。"""

from fastapi import APIRouter, Request, Response, status
from sqlalchemy.exc import SQLAlchemyError

from tara_agent import __version__
from tara_agent.agent.gateway import AgentToolError
from tara_agent.api.schemas import DatasetStatus, HealthResponse, MatouDatasetStatus
from tara_agent.data.reader import ProcessedDataReader
from tara_agent.persistence import Database

router = APIRouter(tags=["service"])


async def _health_response(request: Request) -> HealthResponse:
    reader: ProcessedDataReader | None = request.app.state.data_reader
    database: Database | None = request.app.state.database
    settings = request.app.state.settings
    manifest = reader.manifest if reader is not None else None
    matou_reader = request.app.state.matou_reader
    matou = None
    if matou_reader is not None:
        matou = MatouDatasetStatus(
            dataset_version=matou_reader.manifest.dataset_version,
            taxon=matou_reader.manifest.selection["taxon"],
            sample_counts={
                assay: len(matou_reader.list_samples(assay)) for assay in ("MetaG", "MetaT")
            },
            study_ready=matou_reader.study_sha256 is not None,
            paper_reference_ready=matou_reader.reference_sha256 is not None,
        )
    remote_gateway = request.app.state.remote_gateway
    if remote_gateway is not None:
        try:
            remote_status = await remote_gateway.get_status()
            manifest = remote_status.manifest
            if remote_status.matou is not None:
                remote_matou = remote_status.matou
                matou = MatouDatasetStatus(
                    dataset_version=remote_matou.dataset_version,
                    taxon=remote_matou.taxon,
                    sample_counts=remote_matou.sample_counts,
                    study_ready=remote_matou.study_manifest_sha256 is not None,
                    paper_reference_ready=remote_matou.function_reference_sha256 is not None,
                )
        except AgentToolError:
            manifest = None
            matou = None

    datasets: list[DatasetStatus] = []
    if manifest is not None:
        for key, source in manifest.sources.items():
            sample_count = 0
            if key == "18s_v4":
                sample_count = manifest.coverage.v4_samples
            elif key == "18s_v9":
                sample_count = manifest.coverage.v9_samples
            datasets.append(
                DatasetStatus(
                    key=key,
                    filename=source.filename,
                    ready=True,
                    exists=True,
                    size_bytes=source.size_bytes,
                    column_count=source.column_count,
                    sample_column_count=sample_count,
                    missing_columns=[],
                    duplicate_columns=[],
                    invalid_sample_columns=[],
                )
            )
    data_ready = manifest is not None
    database_ready = await _database_ready(database)
    agent_ready = request.app.state.agent is not None
    persistence_required = settings.environment != "test"
    service_ready = data_ready and agent_ready and (database_ready or not persistence_required)
    return HealthResponse(
        status="ok" if service_ready else "degraded",
        service=settings.app_name,
        version=__version__,
        environment=settings.environment,
        data_ready=data_ready,
        database_ready=database_ready,
        agent_ready=agent_ready,
        model=settings.deepseek_model,
        datasets=datasets,
        matou=matou,
    )


@router.get("/health", response_model=HealthResponse)
async def health(request: Request) -> HealthResponse:
    return await _health_response(request)


@router.get(
    "/ready",
    response_model=HealthResponse,
    responses={status.HTTP_503_SERVICE_UNAVAILABLE: {"model": HealthResponse}},
)
async def ready(request: Request, response: Response) -> HealthResponse:
    payload = await _health_response(request)
    if payload.status != "ok":
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return payload


async def _database_ready(database: Database | None) -> bool:
    if database is None:
        return False
    try:
        await database.ping()
    except (OSError, SQLAlchemyError):
        return False
    return True
