"""比较同一文库的重算和已发布功能谱，不把描述性一致性解释成全局稳定。"""

import json
import math
from pathlib import Path

import polars as pl
from scipy.stats import spearmanr

from tara_agent.analysis.read_models import ReadStudyQuery, ReadStudyResult
from tara_agent.data.matou_reader import MatouDataReader
from tara_agent.data.read_manifest import ReadManifest, sha256
from tara_agent.domain.contracts import DataProvenance, ResultMetadata, ResultWarning
from tara_agent.observability.contracts import ObservationKind, ObservationUpdate
from tara_agent.observability.execution import observe


def compare_profiles(
    baseline: pl.DataFrame, recalculated: pl.DataFrame, mapping: pl.DataFrame, top_n: int
) -> tuple[list[dict], dict]:
    """两个分母都包括未注释的类群基因；同一 gene/Pfam 只累计一次。"""
    profiles = []
    for frame in (baseline, recalculated):
        if (
            frame.is_empty()
            or frame["geneID"].n_unique() != frame.height
            or frame.select(pl.any_horizontal(pl.all().is_null())).to_series().any()
            or frame.filter((pl.col("value") < 0) | ~pl.col("value").is_finite()).height
        ):
            raise ValueError("定量数据为空、重复、缺失或包含无效数值")
        total = math.fsum(frame["value"])
        if total <= 0:
            raise ValueError("没有可用的类群总信号，不能计算功能份额")
        families = (
            frame.join(mapping.select("geneID", "pfamAcc").unique(), on="geneID", how="inner")
            .group_by("pfamAcc")
            .agg(pl.col("value").sum())
            .with_columns((pl.col("value") / total).alias("fraction"))
            .filter(pl.col("fraction") > 0)
            .sort(["fraction", "pfamAcc"], descending=[True, False])
        )
        profiles.append(
            {
                row["pfamAcc"]: (i + 1, row["fraction"])
                for i, row in enumerate(families.iter_rows(named=True))
            }
        )
    published, new = profiles
    if not published or not new:
        raise ValueError("未得到正信号功能，不能比较排名")
    a, b = set(list(published)[:top_n]), set(list(new)[:top_n])
    common = sorted(published.keys() & new.keys())
    x, y = [published[k][1] for k in common], [new[k][1] for k in common]
    rho = (
        float(spearmanr(x, y).statistic)
        if len(common) >= 3 and len(set(x)) > 1 and len(set(y)) > 1
        else None
    )
    rows = []
    for key in sorted(a | b, key=lambda k: (new.get(k, (10**9,))[0], k)):
        old, current = published.get(key), new.get(key)
        rows.append(
            {
                "pfam_accession": key,
                "published_rank": old[0] if old else None,
                "recalculated_rank": current[0] if current else None,
                "published_fraction": old[1] if old else None,
                "recalculated_fraction": current[1] if current else None,
                "difference": current[1] - old[1] if current and old else None,
            }
        )
    return rows, {
        "requested_top_n": top_n,
        "published_top_count": len(a),
        "recalculated_top_count": len(b),
        "top_overlap_count": len(a & b),
        "top_jaccard": len(a & b) / len(a | b),
        "common_observed_families": len(common),
        "spearman_common_families": rho,
        "published_observed_families": len(published),
        "recalculated_observed_families": len(new),
        "assessment": "descriptive_pilot_only_no_global_stability_claim",
    }


class ReadStudyService:
    def __init__(self, directory: Path, reader: MatouDataReader):
        self.directory = directory.resolve(strict=True)
        self.reader = reader

    def analyze(self, query: ReadStudyQuery) -> ReadStudyResult:
        metadata = ResultMetadata(
            provenance=DataProvenance(
                source_datasets=["ena_raw_reads", "matou_pfam", "matou_occurrences"],
                sample_count=0,
                filters={"query": query.model_dump()},
            )
        )
        if query.job_id is None:
            items = []
            for path in sorted(self.directory.glob("*/result.json"))[:100]:
                if path.parent.is_symlink() or path.is_symlink():
                    continue
                # 列表只展示公开标识；实际使用仍须逐项验证摘要与基线。
                record = json.loads(path.read_text(encoding="utf-8"))
                items.append(
                    {
                        "job_id": path.parent.name,
                        "sample_name": record.get("sample_name"),
                        "assay": record.get("assay"),
                        "status": "completed_not_yet_verified",
                    }
                )
            return ReadStudyResult(
                query=query, status="available_jobs", items=items, metadata=metadata
            )
        folder = (self.directory / query.job_id).resolve()
        if folder.parent != self.directory or not folder.is_dir():
            raise ValueError("重算任务不存在；请先查询可用任务")
        with observe(
            "比较原始 reads 重算功能谱",
            ObservationKind.SERVICE,
            ObservationUpdate(input_data=query.model_dump()),
        ) as observation:
            result_path = folder / "result.json"
            record = json.loads(result_path.read_text(encoding="utf-8"))
            if record.get("version") != "read-quantification-v1":
                raise ValueError("不支持的 reads 结果版本")
            for filename in ("profile.parquet", "input.json"):
                path = (folder / filename).resolve()
                if path.parent != folder or sha256(path) != record["artifacts"][filename]:
                    raise ValueError("reads 产物不完整或已变化")
            manifest = ReadManifest.model_validate_json((folder / "input.json").read_text())
            samples = {(r.assay, r.sample_name) for r in manifest.runs}
            if samples != {(record["assay"], record["sample_name"])}:
                raise ValueError("重算输入包含其他文库，不能混合比较")
            if record["matou_manifest_sha256"] != self.reader.manifest_record.sha256:
                raise ValueError("重算绑定的 MATOU 基线已变化，需重新生成")
            if sorted(record["runs"]) != sorted(r.run_accession for r in manifest.runs):
                raise ValueError("重算未包含清单中的全部技术 runs")
            profile = pl.read_parquet(folder / "profile.parquet")
            if profile.schema != {"geneID": pl.Int64, "value": pl.Float64}:
                raise ValueError("重算基因谱格式不匹配")
            if record["reference"]["scope"] == "full_catalogue":
                old = self.reader.load_sample(record["assay"], record["sample_name"])
                mapping = self.reader.load_gene_pfam()
                rows, summary = compare_profiles(
                    old.select("geneID", "value"), profile, mapping, query.top_n
                )
                summary["comparison_status"] = "descriptive_same_taxon_denominator"
            else:
                # 子集参考缺少竞争序列和完整分母，不输出具有误导性的排名一致性统计。
                rows = []
                for qc in record["qc"]:
                    after = qc["after"]["total_reads"]
                    count = qc["statistics"].get("accepted_read_alignments_target_taxon", 0)
                    rows.append(
                        {
                            "run_accession": qc["run"],
                            "qc_read_count": after,
                            "primary_candidate_alignments_before_filters": qc["statistics"].get(
                                "mapped_primary_alignments_before_filters", 0
                            ),
                            "accepted_candidate_read_alignments": count,
                            "candidate_fraction_of_qc_reads": count / after if after else None,
                        }
                    )
                summary = {
                    "comparison_status": "not_comparable_reference_subset",
                    "assessment": "candidate_detection_only_no_stability_claim",
                }
            self.reader.ensure_unchanged()
            summary.update(
                {
                    k: record[k]
                    for k in ("assay", "sample_name", "taxon", "runs", "reference", "method", "qc")
                }
            )
            metadata.provenance.sample_count = 1
            metadata.provenance.filters.update(
                {
                    "result_sha256": sha256(result_path),
                    "manifest_sha256": sha256(folder / "input.json"),
                }
            )
            metadata.warnings.append(
                ResultWarning(
                    code="reads_pilot_not_global_validation",
                    message=(
                        "单文库描述性比较；重算采用独立的唯一比对与质控规则，并非原作者流程复刻。"
                        "功能可共享基因，份额不可相加；缺少记录不补为生物学零值。"
                        "不能据此认定跨环境趋势、DNA/RNA活性或总体结果稳定。"
                    ),
                )
            )
            if manifest.head_pairs_per_run is not None:
                metadata.warnings.append(
                    ResultWarning(
                        code="reads_head_sampling",
                        message="仅抽取各run头部reads对，非随机抽样；未下载完整归档文件，不能验证原始MD5。",
                        details={"head_pairs_per_run": manifest.head_pairs_per_run},
                    )
                )
            if record["reference"]["scope"] != "full_catalogue":
                metadata.warnings.append(
                    ResultWarning(
                        code="reads_subset_reference",
                        message="使用候选序列子集参考，存在竞争比对与分母偏差，不能验证原功能排名。",
                    )
                )
            output = ReadStudyResult(
                query=query,
                status="completed",
                observations=rows,
                summary=summary,
                metadata=metadata,
            )
            observation.finish(
                ObservationUpdate(output_data=output.model_dump(mode="json"), sample_count=1)
            )
            return output
