"""核验样本身份、双端完整性、比对筛选与比较范围，不用合成数据充当科研结果。"""

import io
import json
from types import SimpleNamespace

import polars as pl
import pytest
from mcp import Client
from mcp.server import MCPServer
from pydantic import ValidationError

from tara_agent.analysis.read_models import ReadStudyQuery
from tara_agent.analysis.read_study import ReadStudyService, compare_profiles
from tara_agent.data.read_manifest import ReadFile, sha256
from tara_agent.data.read_pipeline import copy_head_pairs, count_sam, verify_fastq
from tara_agent.mcp.read_tools import register_read_tools


def test_no_path_or_command_in_tool_query():
    for value in ("../job", "/tmp/job", "job;command", "a/b", "a\\b"):
        with pytest.raises(ValidationError):
            ReadStudyQuery(job_id=value)
    with pytest.raises(ValidationError):
        ReadStudyQuery(job_id="pilot", command="anything")


@pytest.mark.parametrize(
    "url",
    [
        "http://ftp.sra.ebi.ac.uk/vol1/fastq/a.fastq.gz",
        "https://localhost/vol1/fastq/a.fastq.gz",
        "https://ftp.sra.ebi.ac.uk/vol1/fastq/../a.fastq.gz",
        "https://ftp.sra.ebi.ac.uk/vol1/fastq/a.fastq.gz?token=x",
    ],
)
def test_download_rejects_non_archive_urls(url):
    with pytest.raises(ValidationError):
        ReadFile(url=url, size_bytes=10, md5="a" * 32)


def test_paired_sampling_preserves_records_and_rejects_mismatch():
    a, b = io.BytesIO(), io.BytesIO()
    first = b"@x/1\nACGT\n+\nIIII\n"
    second = b"@x/2\nTGCA\n+\nIIII\n"
    copy_head_pairs(io.BytesIO(first), io.BytesIO(second), a, b, 1)
    assert a.getvalue() == first and b.getvalue() == second
    with pytest.raises(ValueError, match="编号"):
        copy_head_pairs(io.BytesIO(first), io.BytesIO(second.replace(b"x/2", b"y/2")), a, b, 1)
    with pytest.raises(ValueError, match="不完整"):
        copy_head_pairs(io.BytesIO(first), io.BytesIO(second), a, b, 2)


def test_count_filters_multimapping_identity_and_query_coverage():
    header = "@SQ\tSN:MATOU-v1.5.1\tLN:1000\n"

    def record(flag=0, mapq=40, cigar="100M", nm=0):
        return (
            f"r\t{flag}\tMATOU-v1.5.1\t1\t{mapq}\t{cigar}\t*\t0\t0\t"
            + "A" * 100
            + "\t"
            + "I" * 100
            + f"\tNM:i:{nm}\n"
        )

    lines = [
        header,
        record(),
        record(flag=256),
        record(mapq=0),
        record(mapq=255),
        record(cigar="70M30S"),
        record(nm=6),
    ]
    counts, lengths, stats = count_sam(lines, {1})
    assert counts == {1: 1} and lengths == {1: 1000}
    assert stats["accepted_read_alignments_target_taxon"] == 1
    assert stats["excluded_mapping_quality"] == 2
    assert stats["excluded_identity_or_coverage"] == 2


def test_checksum_failure(tmp_path):
    path = tmp_path / "a.fastq.gz"
    path.write_bytes(b"broken")
    with pytest.raises(ValueError, match="MD5"):
        verify_fastq(path, 6, "a" * 32)


def test_relative_comparison_includes_unannotated_genes_and_deduplicates():
    old = pl.DataFrame({"geneID": [1, 2, 3], "value": [2.0, 1.0, 7.0]})
    new = pl.DataFrame({"geneID": [1, 2, 3], "value": [4.0, 2.0, 14.0]})
    mapping = pl.DataFrame({"geneID": [1, 1, 2], "pfamAcc": ["PF00001"] * 3})
    rows, summary = compare_profiles(old, new, mapping, 20)
    assert len(rows) == 1
    assert rows[0]["published_fraction"] == pytest.approx(0.3)
    assert rows[0]["difference"] == pytest.approx(0)
    assert summary["top_jaccard"] == 1
    assert summary["spearman_common_families"] is None
    assert summary["assessment"] == "descriptive_pilot_only_no_global_stability_claim"


def test_missing_family_is_not_filled_with_zero():
    mapping = pl.DataFrame({"geneID": [1, 2], "pfamAcc": ["PF00001", "PF00002"]})
    rows, summary = compare_profiles(
        pl.DataFrame({"geneID": [1], "value": [1.0]}),
        pl.DataFrame({"geneID": [2], "value": [1.0]}),
        mapping,
        5,
    )
    assert summary["top_jaccard"] == 0
    assert all(row["difference"] is None for row in rows)


def test_zero_or_duplicate_inputs_fail():
    mapping = pl.DataFrame({"geneID": [1], "pfamAcc": ["PF00001"]})
    frame = pl.DataFrame({"geneID": [1], "value": [0.0]})
    with pytest.raises(ValueError, match="总信号"):
        compare_profiles(frame, frame, mapping, 5)
    duplicate = pl.DataFrame({"geneID": [1, 1], "value": [1.0, 1.0]})
    with pytest.raises(ValueError, match="重复"):
        compare_profiles(duplicate, duplicate, mapping, 5)


@pytest.mark.anyio
async def test_read_tool_is_read_only_and_does_not_expose_partial_jobs(tmp_path):
    jobs = tmp_path / "jobs"
    (jobs / "partial").mkdir(parents=True)
    (jobs / "partial" / "input.json").write_text(json.dumps({}))
    server = MCPServer("reads-test")
    register_read_tools(server, ReadStudyService(jobs, None))
    async with Client(server) as client:
        listed = await client.list_tools()
        tool = listed.tools[0]
        assert tool.annotations.read_only_hint and tool.output_schema
        result = await client.call_tool("raw_read_study", {"query": {}})
        assert result.structured_content["items"] == []
        missing = await client.call_tool("raw_read_study", {"query": {"job_id": "missing"}})
        assert missing.is_error


@pytest.fixture
def completed_candidate_job(tmp_path):
    job = tmp_path / "candidate"
    job.mkdir()
    run = "ERR123456"
    manifest = {
        "created_at": "2026-11-11T00:00:00Z",
        "source_sha256": "a" * 64,
        "runs": [
            {
                "run_accession": run,
                "study_accession": "PRJEB4352",
                "experiment_accession": "ERX123456",
                "biosample": "SAMEA123456",
                "sample_name": "TEST11",
                "sample_id": "TEST",
                "assay": "MetaG",
                "library_source": "METAGENOMIC",
                "evidence_row": 3,
                "files": [
                    {
                        "url": f"https://ftp.sra.ebi.ac.uk/vol1/fastq/{run}_{i}.fastq.gz",
                        "size_bytes": 100,
                        "md5": "b" * 32,
                    }
                    for i in (1, 2)
                ],
            }
        ],
    }
    (job / "input.json").write_text(json.dumps(manifest))
    pl.DataFrame({"geneID": [1], "value": [0.1]}).write_parquet(job / "profile.parquet")
    record = {
        "version": "read-quantification-v1",
        "assay": "MetaG",
        "sample_name": "TEST11",
        "taxon": "Bacillariophyta",
        "runs": [run],
        "matou_manifest_sha256": "c" * 64,
        "reference": {"scope": "candidate_subset"},
        "method": {"version": "test"},
        "qc": [
            {
                "run": run,
                "after": {"total_reads": 20},
                "statistics": {"accepted_read_alignments_target_taxon": 2},
            }
        ],
        "artifacts": {name: sha256(job / name) for name in ("input.json", "profile.parquet")},
    }
    (job / "result.json").write_text(json.dumps(record))
    reader = SimpleNamespace(
        manifest_record=SimpleNamespace(sha256="c" * 64), ensure_unchanged=lambda: None
    )
    return job, reader


def test_candidate_result_has_no_misleading_ranking_metrics(completed_candidate_job):
    job, reader = completed_candidate_job
    result = ReadStudyService(job.parent, reader).analyze(ReadStudyQuery(job_id=job.name))
    assert result.summary["comparison_status"] == "not_comparable_reference_subset"
    assert "top_jaccard" not in result.summary
    assert result.observations[0]["candidate_fraction_of_qc_reads"] == pytest.approx(0.1)
    assert any(w.code == "reads_subset_reference" for w in result.metadata.warnings)


def test_changed_profile_and_changed_baseline_rejected(completed_candidate_job):
    job, reader = completed_candidate_job
    service = ReadStudyService(job.parent, reader)
    reader.manifest_record.sha256 = "d" * 64
    with pytest.raises(ValueError, match="基线"):
        service.analyze(ReadStudyQuery(job_id=job.name))
    reader.manifest_record.sha256 = "c" * 64
    (job / "profile.parquet").write_bytes(b"changed")
    with pytest.raises(ValueError, match="已变化"):
        service.analyze(ReadStudyQuery(job_id=job.name))
