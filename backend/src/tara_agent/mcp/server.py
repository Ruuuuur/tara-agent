"""MCP 服务工厂和标准输入输出入口。"""

from pathlib import Path

from mcp.server import MCPServer

from tara_agent.analysis import TaraComputeService, TaraQueryService
from tara_agent.analysis.function_service import MatouFunctionService
from tara_agent.analysis.read_study import ReadStudyService
from tara_agent.config import get_settings
from tara_agent.data.matou_reader import MatouDataReader
from tara_agent.data.reader import ProcessedDataReader
from tara_agent.data.research_context import ResearchContext
from tara_agent.mcp.catalog import register_catalog
from tara_agent.mcp.function_tools import register_function_tools
from tara_agent.mcp.read_tools import register_read_tools
from tara_agent.mcp.research_tools import register_research_tools
from tara_agent.mcp.tools import register_tools
from tara_agent.mcp.transport import TaraMCPServer


def create_server(
    reader: ProcessedDataReader | None = None,
    *,
    matou_reader: MatouDataReader | None = None,
    research: ResearchContext | None = None,
    read_jobs_dir: Path | None = None,
) -> MCPServer:
    """基于一个已校验的处理后数据读取器创建 Tara MCP 服务。"""

    if reader is None:
        settings = get_settings()
        reader = ProcessedDataReader(settings.processed_data_dir)
        if settings.matou_data_dir is not None:
            matou_reader = MatouDataReader(settings.matou_data_dir)
        read_jobs_dir = settings.read_jobs_dir

    research = research or ResearchContext(reader.processed_dir)
    server = TaraMCPServer(
        data_context={
            "core_generation": reader.manifest.generation,
            "core_pipeline_version": reader.manifest.pipeline_version,
            "matou_manifest_sha256": matou_reader.manifest_record.sha256 if matou_reader else None,
            "research_manifest_sha256": research.sha256,
        },
        name="tara-agent",
        title="Tara Agent",
        version="0.1.0",
        instructions=(
            "Query and analyze validated Tara Oceans data using available tools. "
            "V4 and V9 require an explicit marker and remain independent. "
            "MATOU requires an explicit MetaG/MetaT assay and original sample name; "
            "candidate function signals do not establish physical units or DNA/RNA pairing. "
            "Pass tool arguments as JSON objects (most tools take a nested query object). "
            "Preserve metadata.warnings and metadata.provenance in your answer. "
            "Read tara://data/catalog for configured data versions and source hashes. "
            "An isError result is a failed call, not an empty scientific result."
        ),
    )
    register_tools(
        server,
        query_service=TaraQueryService(reader),
        compute_service=TaraComputeService(reader),
    )
    if matou_reader is not None:
        register_function_tools(server, MatouFunctionService(matou_reader))
        if read_jobs_dir is not None:
            register_read_tools(server, ReadStudyService(read_jobs_dir, matou_reader))
    register_research_tools(server, reader, matou_reader, research)
    register_catalog(server, reader, matou_reader, research)
    return server


def main() -> None:
    """通过标准输入输出传输方式运行 Tara MCP 服务。"""

    from tara_agent.mcp.cli import main as run

    run()
