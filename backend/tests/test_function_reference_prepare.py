"""参考资料缺失、损坏、重复部署与准备失败不会产生虚假的可用能力。"""

import gzip
import json
import runpy
from pathlib import Path

import pytest

from tara_agent.agent.gateway import MCPToolGateway
from tara_agent.agent.models import ToolName
from tara_agent.data.function_reference import FunctionReference
from tara_agent.data.matou_reader import MatouDataReader
from tara_agent.data.reader import ProcessedDataReader
from tara_agent.mcp import create_server

from .test_data_service import service_settings as service_settings
from .test_function_atlas import cohort as cohort
from .test_function_study import reference_bundle, select_diatoms
from .test_matou_function_data import dataset as dataset

SCRIPT = Path(__file__).resolve().parents[1] / "deploy/prepare_function_reference.py"


@pytest.fixture
def cli():
    return runpy.run_path(str(SCRIPT))["main"]


@pytest.fixture
def sources(tmp_path):
    path = tmp_path / "sources"
    path.mkdir()
    tables = {
        "PfamA.list": "accession\tname\tdescription\nPF00001\ta\tRibosomal protein A\n",
        "station_ocean.tsv": "station\tocean\n1\tAO\n",
        "physicochemistry.for.metaT.tsv": "station\tdepth\tTemperature\n1\tSUR\t10\n",
        "station_Lat_Long_uniq.withTaraPrefix.tsv": "station\tlat\tlon\n1\t60\t10\n",
        "Bacillariophyta.MATOU-v1.5.Pfam.metaG.tsv.gz": (
            "sample\tpfamAcc\trpkm\n1SUR1GGMM11\tPF00001\t2.0\n"
        ),
        "Bacillariophyta.MATOU-v1.5.Pfam.metaT.tsv.gz": (
            "sample\tpfamAcc\trpkm\n1SUR1GGMM14\tPF00001\t3.0\n"
        ),
        "LHC.diatoms.MATOUv1.5.seqs.function.tsv.gz": ("unigene\tLHCtype\nMATOU-v1.5.1\tLHCf\n"),
    }
    for name, text in tables.items():
        if name.endswith(".gz"):
            with gzip.open(path / name, "wt", encoding="utf-8") as stream:
                stream.write(text)
        else:
            (path / name).write_text(text, encoding="utf-8")
    return path


def test_prepare_then_check_and_reuse_without_network(cli, sources, tmp_path, monkeypatch):
    output = tmp_path / "reference"
    cli(["--source-dir", str(sources), "--output-dir", str(output)])
    reference = FunctionReference(output)
    reference.validate()
    assert reference.frame("MetaT")["rpkm"].to_list() == [3.0]
    before = {p.name: p.read_bytes() for p in output.iterdir()}

    def forbidden(*args, **kwargs):
        pytest.fail("已有完整资料不得重新下载或预处理")

    monkeypatch.setitem(cli.__globals__, "download_sources", forbidden)
    monkeypatch.setitem(cli.__globals__, "prepare_reference", forbidden)
    cli(["--output-dir", str(output), "--check"])
    cli(["--output-dir", str(output), "--download"])
    assert {p.name: p.read_bytes() for p in output.iterdir()} == before


def test_check_missing_bundle_does_not_create_directory(cli, tmp_path):
    matou = tmp_path / "matou"
    with pytest.raises(SystemExit) as error:
        cli(["--matou-dir", str(matou), "--check"])
    assert error.value.code == 2
    assert not matou.exists()


@pytest.mark.parametrize("damage", ["content", "missing_key", "missing_file", "version"])
def test_invalid_existing_bundle_is_never_overwritten(cli, tmp_path, damage):
    reference = reference_bundle(tmp_path / "reference")
    manifest_path = reference.directory / "manifest.json"
    if damage == "content":
        path = reference.directory / "pfam.parquet"
        path.write_bytes(path.read_bytes() + b"tamper")
    elif damage == "missing_key":
        del reference.manifest["files"]["pfam"]
        manifest_path.write_text(json.dumps(reference.manifest), encoding="utf-8")
    elif damage == "missing_file":
        (reference.directory / "pfam.parquet").rename(reference.directory / "pfam.saved")
    else:
        reference.manifest["author_commit"] = "wrong-version"
        manifest_path.write_text(json.dumps(reference.manifest), encoding="utf-8")
    before = {p.name: p.read_bytes() for p in reference.directory.iterdir()}
    with pytest.raises(SystemExit) as error:
        cli(["--output-dir", str(reference.directory), "--download"])
    assert error.value.code == 2
    assert {p.name: p.read_bytes() for p in reference.directory.iterdir()} == before


def test_failed_preparation_does_not_publish_partial_bundle(cli, sources, tmp_path):
    # 最后一个输入不可解析时，前面已转换的文件也不能成为正式资料包。
    with gzip.open(sources / "LHC.diatoms.MATOUv1.5.seqs.function.tsv.gz", "wt") as stream:
        stream.write("unigene\tLHCtype\nMATOU-v1.5.1\tLHCf\nMATOU-v1.5.1\tLHCx\n")
    output = tmp_path / "reference"
    with pytest.raises(SystemExit):
        cli(["--source-dir", str(sources), "--output-dir", str(output)])
    assert not output.exists()
    assert not list(tmp_path.glob(".function-reference-*"))


def test_lhc_cache_for_another_matou_version_is_rejected(cli, cohort):
    reference = reference_bundle(cohort / "paper_task2")
    reference.manifest["files"]["lhc_profiles"] = reference.manifest["files"]["pfam"]
    reference.manifest["lhc_source_manifest_sha256"] = "0" * 64
    (reference.directory / "manifest.json").write_text(json.dumps(reference.manifest))
    with pytest.raises(SystemExit):
        cli(["--matou-dir", str(cohort), "--check"])


@pytest.mark.anyio
async def test_missing_reference_keeps_other_tools_and_enables_study_after_restart(
    cohort, service_settings
):
    select_diatoms(cohort)
    core = ProcessedDataReader(service_settings.processed_data_dir)
    gateway = MCPToolGateway(create_server(core, matou_reader=MatouDataReader(cohort)))
    names = {tool.name for tool in await gateway.list_tools()}
    assert ToolName.FUNCTION_STUDY not in names
    assert {ToolName.FUNCTION_ATLAS, ToolName.FUNCTION_PROFILE} <= names
    reference_bundle(cohort / "paper_task2")
    restarted = MCPToolGateway(create_server(core, matou_reader=MatouDataReader(cohort)))
    assert ToolName.FUNCTION_STUDY in {tool.name for tool in await restarted.list_tools()}
    result = await restarted.call(
        ToolName.FUNCTION_STUDY, {"query": {"include_environment": False}}
    )
    assert result["function_ranks"][0]["function_name"] == "Ribosomal proteins"
    assert result["sample_group_count"] > 0
