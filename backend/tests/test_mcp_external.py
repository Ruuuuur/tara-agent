"""真实独立进程的 MCP 验收：发现、科学结果一致、来源以及失败后继续调用。"""

import csv
import hashlib
import json
import math
import subprocess
import sys
from contextlib import asynccontextmanager
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator
from mcp import Client
from mcp.client.stdio import StdioServerParameters

from tara_agent.analysis import TaraComputeService, TaraQueryService
from tara_agent.analysis.community import CommunityService
from tara_agent.analysis.community_models import CommunityQuery
from tara_agent.analysis.compute_models import (
    DiversityQuery,
    EnvironmentAssociationQuery,
    TaxonAbundanceQuery,
)
from tara_agent.analysis.function_atlas import MatouAtlasService
from tara_agent.analysis.function_atlas_models import AtlasQuery
from tara_agent.analysis.function_query_models import FunctionProfileQuery, FunctionSamplesQuery
from tara_agent.analysis.function_service import MatouFunctionService
from tara_agent.analysis.models import FindSamplesQuery, FindTaxaQuery
from tara_agent.data.matou_prepare import PreparationLimits, prepare_function_data
from tara_agent.data.matou_reader import MatouDataReader
from tara_agent.data.preprocess import preprocess
from tara_agent.data.reader import ProcessedDataReader
from tara_agent.mcp import create_server
from tara_agent.mcp.transport import CATALOG_URI, META_KEY

from .test_matou_function_data import dataset as dataset


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
def processed(preprocessable_dataset_dir, tmp_path):
    # 非对称的双 ASV 读数，验证实际分母、非零 Shannon 和两个标记彼此独立。
    for marker, counts in (("V4", (3, 0)), ("V9", (0, 4))):
        source = next(preprocessable_dataset_dir.glob(f"*18S-{marker}_*.tsv"))
        with source.open(encoding="utf-8", newline="") as stream:
            rows = list(csv.DictReader(stream, delimiter="\t"))
        other = {
            **rows[0],
            "amplicon": "f" * 32,
            "taxonomy": "Root;Eukaryota;Bacillariophyta",
            "total": str(sum(counts)),
            "spread": "1",
            "TARA_TEST_001": str(counts[0]),
            "TARA_TEST_002": str(counts[1]),
        }
        if marker == "V9":
            rows[0].update({"TARA_TEST_001": "2", "TARA_TEST_002": "1"})
        with source.open("w", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(rows[0]), delimiter="\t")
            writer.writeheader()
            writer.writerows([*rows, other])
    directory = tmp_path / "processed"
    preprocess(preprocessable_dataset_dir, directory, enforce_expected_shape=False)
    return ProcessedDataReader(directory)


@asynccontextmanager
async def external_client(reader, cwd, matou=None, *, entry="module"):
    args = ["-m", "tara_agent.mcp"] if entry == "module" else []
    command = (
        sys.executable if entry == "module" else str(Path(sys.executable).with_name("tara-mcp"))
    )
    args += ["--processed-data-dir", str(reader.processed_dir)]
    args += ["--matou-data-dir", str(matou)] if matou else ["--core-only"]
    # 与产品内 Client(server) 不同：执行命令、跨进程交换标准 JSON-RPC 消息。
    params = StdioServerParameters(command=command, args=args, cwd=cwd)
    async with Client(
        params, read_timeout_seconds=30, mode="legacy" if entry == "console" else "auto"
    ) as client:
        yield client


@pytest.mark.anyio
@pytest.mark.parametrize("entry", ["module", "console"])
async def test_external_discovery_and_source_catalog(processed, tmp_path, entry):
    async with external_client(processed, tmp_path, entry=entry) as client:
        tools = (await client.list_tools()).tools
        assert {t.name for t in tools} == {
            "find_samples",
            "get_sample_info",
            "find_taxa",
            "taxon_abundance",
            "diversity_analysis",
            "environment_association",
            "community_analysis",
        }
        for tool in tools:
            assert tool.description and tool.annotations.read_only_hint
            assert tool.annotations.open_world_hint is False
            assert tool.input_schema["additionalProperties"] is False
            Draft202012Validator.check_schema(tool.input_schema)
            Draft202012Validator.check_schema(tool.output_schema)
            arguments = next(iter(tool.input_schema["properties"].values()))
            assert arguments["examples"]
        resources = await client.list_resources()
        assert CATALOG_URI in {str(r.uri) for r in resources.resources}
        catalog = json.loads((await client.read_resource(CATALOG_URI)).contents[0].text)
        assert catalog["core"]["generation"] == processed.manifest.generation
        assert catalog["matou"] is None and catalog["research"] is None
        for key, record in catalog["core"]["sources"].items():
            path = tmp_path / "source" / record["filename"]
            assert record["sha256"] == hashlib.sha256(path.read_bytes()).hexdigest()
            assert record["sha256"] == processed.manifest.sources[key].sha256
        assert str(tmp_path) not in json.dumps(catalog)


@pytest.mark.anyio
@pytest.mark.parametrize("marker", ["v4", "v9"])
async def test_external_calculations_equal_direct_scientific_services(processed, tmp_path, marker):
    query = TaraQueryService(processed)
    compute = TaraComputeService(processed)
    requests = [
        (
            "find_samples",
            {"query": {"depths": ["表层"], "limit": 1}},
            query.find_samples(FindSamplesQuery(depths=["表层"], limit=1)),
        ),
        ("get_sample_info", {"sample_id": "TARA_TEST_001"}, query.get_sample_info("TARA_TEST_001")),
        (
            "find_taxa",
            {"query": {"marker": marker, "taxon": "Dinoflagellata"}},
            query.find_taxa(FindTaxaQuery(marker=marker, taxon="Dinoflagellata")),
        ),
        (
            "taxon_abundance",
            {"query": {"marker": marker, "taxon": "Dinoflagellata"}},
            compute.taxon_abundance(TaxonAbundanceQuery(marker=marker, taxon="Dinoflagellata")),
        ),
        (
            "diversity_analysis",
            {"query": {"marker": marker, "group_by": "depth"}},
            compute.diversity_analysis(DiversityQuery(marker=marker, group_by="depth")),
        ),
        (
            "environment_association",
            {
                "query": {
                    "marker": marker,
                    "taxon": "Dinoflagellata",
                    "environment_variable": "temperature",
                }
            },
            compute.environment_association(
                EnvironmentAssociationQuery(
                    marker=marker, taxon="Dinoflagellata", environment_variable="temperature"
                )
            ),
        ),
    ]
    community = CommunityQuery(
        markers=[marker],
        taxon="Dinoflagellata",
        outputs=["distribution", "diversity"],
        environment_source="context_stat",
    )
    requests.append(
        (
            "community_analysis",
            {"query": community.model_dump(mode="json")},
            CommunityService(processed).analyze(community),
        )
    )
    async with external_client(processed, tmp_path) as client:
        tools = {t.name: t for t in (await client.list_tools()).tools}
        for name, arguments, direct in requests:
            response = await client.call_tool(name, arguments)
            assert not response.is_error, response.content
            assert response.structured_content == direct.model_dump(mode="json")
            Draft202012Validator(tools[name].output_schema).validate(response.structured_content)
            assert response.structured_content["metadata"]["provenance"]["source_datasets"]
            assert response.meta[META_KEY]["catalog_uri"] == CATALOG_URI
            assert response.meta[META_KEY]["configured_data"]["core_generation"] == (
                processed.manifest.generation
            )
            # 兼容仅消费 TextContent 的 MCP 客户端，不能只返回 Python 模型。
            assert json.loads(response.content[0].text) == response.structured_content
            if name == "taxon_abundance":
                first = response.structured_content["observations"][0]
                expected_reads, expected_total = (1, 4) if marker == "v4" else (2, 2)
                assert first["taxon_read_count"] == expected_reads
                assert first["sample_total_read_count"] == expected_total
                assert first["relative_abundance"] == pytest.approx(expected_reads / expected_total)
            if name == "diversity_analysis":
                observations = response.structured_content["observations"]
                expected_richness = [2, 1] if marker == "v4" else [1, 2]
                assert [o["observed_asv_richness"] for o in observations] == expected_richness
                nonzero = observations[0 if marker == "v4" else 1]["shannon_index"]
                fraction = 0.25 if marker == "v4" else 0.2
                assert nonzero == pytest.approx(
                    -fraction * math.log(fraction) - (1 - fraction) * math.log(1 - fraction)
                )
            if name == "environment_association":
                # 样本数不足不能伪装成有效相关；原因必须跨传输保留。
                assert response.structured_content["metadata"]["warnings"]


@pytest.mark.anyio
async def test_external_errors_are_actionable_and_session_remains_usable(processed, tmp_path):
    cases = [
        ("execute_sql", {}, "unknown_tool"),
        ("find_samples", {"query": {}, "sql": "select secret"}, "invalid_arguments"),
        ("find_samples", {"query": {"limit": 501}}, "invalid_arguments"),
        ("find_samples", {"query": {"temperature_min": "NaN"}}, "invalid_arguments"),
        (
            "find_samples",
            {"query": {"temperature_min": 30, "temperature_max": 20}},
            "invalid_arguments",
        ),
        ("find_taxa", {"query": {"marker": "v18", "taxon": "Eukaryota"}}, "invalid_arguments"),
        ("diversity_analysis", {"query": {}}, "invalid_arguments"),
        ("diversity_analysis", {"query": {"marker": "v4", "sample_ids": []}}, "invalid_arguments"),
        ("taxon_abundance", {"query": {"marker": "v4", "taxon": "  "}}, "invalid_arguments"),
        ("get_sample_info", {"sample_id": "not-a-sample"}, "not_found"),
        (
            "taxon_abundance",
            {"query": {"marker": "v4", "taxon": "Eukaryota", "sample_ids": ["not-a-sample"]}},
            "analysis_error",
        ),
    ]
    async with external_client(processed, tmp_path) as client:
        for name, arguments, expected in cases:
            response = await client.call_tool(name, arguments)
            assert response.is_error and response.structured_content is None
            context = response.meta[META_KEY]
            assert context["tool"] == name and context["catalog_uri"] == CATALOG_URI
            assert context["error"]["code"] == expected
            assert response.content[0].text
            if expected == "invalid_arguments":
                assert context["error"]["fields"]
                assert all("input" not in field for field in context["error"]["fields"])
        valid = await client.call_tool("find_samples", {"query": {"limit": 1}})
        assert not valid.is_error and len(valid.structured_content["items"]) == 1


@pytest.mark.anyio
async def test_unexpected_failure_hides_exception_and_recovers(processed, caplog):
    server = create_server(processed)

    @server.tool()
    def deliberate_failure() -> dict:
        raise RuntimeError("private-password-and-internal-path")

    async with Client(server) as client:
        failure = await client.call_tool("deliberate_failure", {})
        assert failure.is_error
        assert failure.meta[META_KEY]["error"]["code"] == "internal_error"
        assert "private-password" not in failure.model_dump_json()
        assert "private-password" in caplog.text
        assert not (await client.call_tool("find_samples", {"query": {}})).is_error


def test_invalid_data_fails_startup_without_polluting_protocol_stdout(tmp_path):
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "tara_agent.mcp",
            "--core-only",
            "--processed-data-dir",
            str(tmp_path / "missing"),
        ],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        timeout=15,
        check=False,
    )
    assert result.returncode == 2 and result.stdout == ""
    assert "Tara MCP startup failed" in result.stderr


@pytest.mark.anyio
async def test_conditional_matou_discovery_parity_and_missing_prerequisite(
    processed, dataset, tmp_path
):
    prepare_function_data(*dataset, PreparationLimits(min_free_gib=0))
    reader = MatouDataReader(dataset[3])
    service = MatouFunctionService(reader)
    requests = [
        (
            "find_function_samples",
            FunctionSamplesQuery(assay="MetaG", limit=1),
            service.find_samples,
        ),
        (
            "function_profile",
            FunctionProfileQuery(assay="MetaG", sample_name="G-A"),
            service.function_profile,
        ),
        ("function_atlas", AtlasQuery(assay="MetaG"), MatouAtlasService(reader).atlas),
    ]
    async with external_client(processed, tmp_path, dataset[3]) as client:
        tools = {t.name for t in (await client.list_tools()).tools}
        assert "function_profile" in tools and "function_study" not in tools
        catalog = json.loads((await client.read_resource(CATALOG_URI)).contents[0].text)
        assert catalog["matou"]["manifest_sha256"] == reader.manifest_record.sha256
        assert catalog["matou"]["selection"]["taxon"] == "Example taxon"
        for name, query, direct in requests:
            response = await client.call_tool(name, {"query": query.model_dump(mode="json")})
            assert not response.is_error and response.structured_content == direct(
                query
            ).model_dump(mode="json")
        sequences = await client.call_tool("retrieve_gene_sequences", {"query": {"gene_ids": [1]}})
        assert sequences.is_error and sequences.meta[META_KEY]["error"]["code"] == "analysis_error"
