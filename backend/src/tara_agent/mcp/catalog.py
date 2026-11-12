"""将已加载的数据版本与来源通过只读 MCP resource 提供给外部客户端。"""

import json
from pathlib import Path

from mcp.server import MCPServer

from tara_agent.data.matou_reader import MatouDataReader
from tara_agent.data.reader import ProcessedDataReader
from tara_agent.data.research_context import ResearchContext
from tara_agent.mcp.transport import CATALOG_URI


def register_catalog(
    server: MCPServer,
    reader: ProcessedDataReader,
    matou: MatouDataReader | None,
    research: ResearchContext,
) -> None:
    @server.resource(
        CATALOG_URI,
        name="tara_data_catalog",
        mime_type="application/json",
        description=(
            "Configured data versions and SHA-256 source records. This is an inventory, "
            "not a claim that every configured dataset was used. Each tool result's "
            "metadata.provenance lists its actual sources and filters."
        ),
    )
    def data_catalog() -> str:
        manifest = reader.manifest
        result = {
            "contract_version": 1,
            "core": {
                "generation": manifest.generation,
                "pipeline_version": manifest.pipeline_version,
                "sources": {
                    key: record.model_dump(mode="json") for key, record in manifest.sources.items()
                },
                "artifacts": {
                    key: record.model_dump(
                        mode="json",
                        exclude={
                            "fixed_schema",
                            "repeated_columns",
                            "repeated_column_type",
                        },
                    )
                    for key, record in manifest.artifacts.items()
                },
            },
            "matou": None,
            "research": None,
        }
        if matou is not None:
            result["matou"] = {
                "dataset_version": matou.manifest.dataset_version,
                "pipeline_version": matou.manifest.pipeline_version,
                "selection": matou.manifest.selection,
                "manifest_sha256": matou.manifest_record.sha256,
                "study_manifest_sha256": matou.study_sha256,
                "function_reference_sha256": matou.reference_sha256,
                "sources": {
                    key: {
                        "filename": Path(record.path).name,
                        "size_bytes": record.size_bytes,
                        "sha256": record.sha256,
                    }
                    for key, record in matou.manifest.source_files.items()
                },
            }
        if research.manifest is not None:
            result["research"] = {
                "manifest_sha256": research.sha256,
                "version": research.manifest["version"],
                "core_generation": research.manifest["core_generation"],
                "sources": {
                    key: {
                        "source": value["source"],
                        "version": value["version"],
                        "filename": Path(value["file"]["path"]).name,
                        "sha256": value["file"]["sha256"],
                    }
                    for key, value in research.manifest["sources"].items()
                },
            }
        return json.dumps(result, ensure_ascii=False, allow_nan=False)
