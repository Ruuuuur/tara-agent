"""管理员离线运行的有界试点：ENA下载、fastp质控、Bowtie2比对及长度归一化。"""

import argparse
import gzip
import hashlib
import json
import os
import re
import shutil
import signal
import subprocess
import threading
import urllib.request
from collections import Counter
from contextlib import suppress
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlsplit

import polars as pl
import psutil

from tara_agent.data.matou_reader import MatouDataReader
from tara_agent.data.matou_study import load_sequences
from tara_agent.data.read_manifest import (
    ReadManifest,
    SampledReadFile,
    plan_reads,
    sha256,
    write_json_new,
)


def load_manifest(path: Path) -> ReadManifest:
    return ReadManifest.model_validate_json(path.read_text(encoding="utf-8"))


def verify_fastq(path: Path, size: int, digest: str) -> None:
    if path.stat().st_size != size:
        raise ValueError(f"FASTQ 大小不符：{path.name}")
    with path.open("rb") as stream:
        if hashlib.file_digest(stream, "md5").hexdigest() != digest:
            raise ValueError(f"FASTQ MD5 不符：{path.name}")


def copy_head_pairs(first, second, output_first, output_second, pairs: int) -> None:
    """读取完整FASTQ记录并逐对核对；头部抽取只作工程试点，不称随机样本。"""
    for _ in range(pairs):
        reads = [[stream.readline() for _ in range(4)] for stream in (first, second)]
        ids = []
        for record in reads:
            if (
                any(not line.endswith(b"\n") for line in record)
                or not record[0].startswith(b"@")
                or not record[2].startswith(b"+")
                or len(record[1].rstrip()) != len(record[3].rstrip())
            ):
                raise ValueError("FASTQ不完整、提前结束或序列/质量长度不同")
            ident = record[0].split()[0][1:]
            ids.append(re.sub(rb"/[12]$", b"", ident))
        if ids[0] != ids[1]:
            raise ValueError("FASTQ双端reads编号不一致")
        for output, record in zip((output_first, output_second), reads, strict=True):
            output.writelines(record)


def sample_reads(manifest: ReadManifest, directory: Path, pairs: int) -> ReadManifest:
    if manifest.head_pairs_per_run is not None:
        raise ValueError("不允许对抽样清单再次抽样")
    if not 1 <= pairs <= 1000000:
        raise ValueError("首版每run抽取1到100万对reads")
    directory.mkdir(parents=True, exist_ok=False)
    sampled = {}
    for run in manifest.runs:
        paths = [directory / f"{run.run_accession}_{i}.sample.fastq.gz" for i in (1, 2)]
        with (
            urllib.request.urlopen(run.files[0].url, timeout=120) as a,
            urllib.request.urlopen(run.files[1].url, timeout=120) as b,
        ):
            if any(
                not response.geturl().startswith("https://ftp.sra.ebi.ac.uk/")
                for response in (a, b)
            ):
                raise ValueError("拒绝非 ENA 下载重定向")
            with (
                gzip.GzipFile(fileobj=a) as first,
                gzip.GzipFile(fileobj=b) as second,
                gzip.open(paths[0], "xb") as out_a,
                gzip.open(paths[1], "xb") as out_b,
            ):
                copy_head_pairs(first, second, out_a, out_b, pairs)
        files = []
        for path in paths:
            with path.open("rb") as stream:
                digest = hashlib.file_digest(stream, "md5").hexdigest()
            files.append(
                SampledReadFile(
                    filename=path.name,
                    size_bytes=path.stat().st_size,
                    md5=digest,
                    sha256=sha256(path),
                )
            )
        sampled[run.run_accession] = files
        print(f"sampled {run.run_accession}: {pairs} head pairs", flush=True)
    return ReadManifest.model_validate(
        {**manifest.model_dump(), "head_pairs_per_run": pairs, "sampled_files": sampled}
    )


def download(manifest: ReadManifest, directory: Path, max_gb: float) -> None:
    """按完整文件下载，不用截断 FASTQ 冒充完整测序数据。"""
    directory.mkdir(parents=True, exist_ok=True)
    if manifest.head_pairs_per_run is not None:
        raise ValueError("完整下载必须使用原始ENA清单")
    files = [f for run in manifest.runs for f in run.files]
    total = sum(f.size_bytes for f in files)
    if total > max_gb * 1024**3:
        raise ValueError(f"清单共 {total / 1024**3:.2f} GiB，超过下载上限 {max_gb} GiB")
    needed = sum(
        f.size_bytes for f in files if not (directory / Path(urlsplit(f.url).path).name).exists()
    )
    if shutil.disk_usage(directory).free < needed + 2 * 1024**3:
        raise ValueError("可用磁盘不足，拒绝启动下载")
    for file in files:
        path = directory / Path(urlsplit(file.url).path).name
        if path.is_symlink():
            raise ValueError("不允许 FASTQ 符号链接")
        if not path.exists():
            temporary = path.with_suffix(path.suffix + ".partial")
            with urllib.request.urlopen(file.url, timeout=120) as response:
                if not response.geturl().startswith("https://ftp.sra.ebi.ac.uk/"):
                    raise ValueError("拒绝非 ENA 下载重定向")
                with temporary.open("xb") as output:
                    size = 0
                    while block := response.read(1024**2):
                        size += len(block)
                        if size > file.size_bytes:
                            raise ValueError("下载超过清单大小")
                        output.write(block)
            verify_fastq(temporary, file.size_bytes, file.md5)
            temporary.rename(path)
        verify_fastq(path, file.size_bytes, file.md5)
        print(f"verified {path.name}", flush=True)


def checked_command(arguments: list[str], log: Path, hours: float) -> None:
    with (
        log.open("x", encoding="utf-8") as output,
        subprocess.Popen(arguments, stdout=output, stderr=subprocess.STDOUT,
                         start_new_session=os.name != "nt") as process,
    ):
        try:
            code = process.wait(timeout=hours * 3600)
            if code:
                raise subprocess.CalledProcessError(code, arguments)
        except BaseException:
            kill_process_tree(process)
            process.wait()
            raise


def kill_process_tree(process) -> None:
    if process.poll() is not None:
        return
    if os.name != "nt":
        with suppress(ProcessLookupError):
            os.killpg(process.pid, signal.SIGKILL)
    else:
        for child in psutil.Process(process.pid).children(recursive=True):
            with suppress(psutil.NoSuchProcess):
                child.kill()
        process.kill()


def tool_version(name: str) -> str:
    result = subprocess.run(
        [name, "--version"], capture_output=True, text=True, check=True, timeout=30
    )
    return (result.stdout + result.stderr).strip()[:2000]


def build_index(reference: Path, output: Path, scope: str, threads: int, hours: float) -> None:
    sidecar = reference.with_suffix(reference.suffix + ".json")
    if sidecar.exists() and json.loads(sidecar.read_text())["scope"] != scope:
        raise ValueError("参考范围与导出来源不符，候选子集不能标记为完整目录")
    if reference.suffix == ".gz":
        raise ValueError("请先在服务器独立目录解压完整 FASTA，索引不覆盖或改写原始文件")
    # 粗略预检只用于拒绝明显不足的机器；正式执行仍须容器内存/CPU配额。
    size = reference.stat().st_size
    if psutil.virtual_memory().available < max(512 * 1024**2, size * 2):
        raise ValueError("参考索引的保守内存预检未通过，请缩小候选试点或换计算环境")
    output.parent.mkdir(parents=True, exist_ok=True)
    if shutil.disk_usage(output.parent).free < max(1024**3, size * 6):
        raise ValueError("参考索引的预留磁盘不足")
    output.mkdir(exist_ok=False)
    before = sha256(reference)
    checked_command(
        ["bowtie2-build", "--threads", str(threads), str(reference), str(output / "catalogue")],
        output / "build.log",
        hours,
    )
    artifacts = sorted(output.glob("catalogue*.bt2*"))
    if len(artifacts) != 6 or sha256(reference) != before:
        raise ValueError("索引不完整或参考文件已变化")
    write_json_new(
        output / "index.json",
        {
            "version": "read-index-v1",
            "reference_sha256": before,
            "scope": scope,
            "reference_name": reference.name,
            "bowtie2_build": tool_version("bowtie2-build"),
            "artifacts": {f.name: sha256(f) for f in artifacts},
            "source": json.loads(sidecar.read_text()) if sidecar.exists() else None,
        },
    )


def export_reference(matou_dir: Path, pfam: str, output: Path) -> None:
    if not re.fullmatch(r"PF[0-9]{5}", pfam):
        raise ValueError("Pfam格式无效")
    reader = MatouDataReader(matou_dir)
    sequences, provenance = load_sequences(reader)
    genes = reader.load_gene_pfam().filter(pl.col("pfamAcc") == pfam).select("geneID").unique()
    selected = sequences.join(genes, on="geneID", how="semi").sort("geneID")
    if not selected.height:
        raise ValueError("该Pfam没有已经核验的序列，不能建立试点参考")
    with output.open("x", encoding="ascii", newline="\n") as stream:
        for row in selected.iter_rows(named=True):
            if gene_id(row["header"]) != row["geneID"]:
                raise ValueError("序列标题与基因标识不符")
            stream.write(f">{row['header']}\n{row['sequence']}\n")
    write_json_new(
        output.with_suffix(output.suffix + ".json"),
        {
            "scope": "candidate_subset",
            "pfam": pfam,
            "genes": selected.height,
            "reference_sha256": sha256(output),
            "source": provenance,
            "matou_manifest_sha256": reader.manifest_record.sha256,
        },
    )
    print(f"candidate-only reference: {selected.height} genes; {output}")


def gene_id(name: str) -> int:
    match = re.fullmatch(r"MATOU-v1\.5\.(\d+)", name)
    if not match:
        raise ValueError("参考标题必须是 MATOU-v1.5.<geneID>；不猜测其他序列命名")
    return int(match[1])


def count_sam(lines, selected: set[int]) -> tuple[Counter, dict[int, int], Counter]:
    """按 read/mate 而非 fragment 计数；排除低MAPQ与次要比对，不分配多重比对。"""
    counts, lengths, stats = Counter(), {}, Counter()
    for line in lines:
        fields = line.rstrip("\n").split("\t")
        if line.startswith("@"):
            if fields[0] == "@SQ":
                header = dict(value.split(":", 1) for value in fields[1:])
                ident = gene_id(header["SN"])
                if ident in selected:
                    length = int(header["LN"])
                    if ident in lengths or length <= 0:
                        raise ValueError("参考基因重复或长度无效")
                    lengths[ident] = length
            continue
        if len(fields) < 11:
            raise ValueError("SAM 记录不完整")
        flag, mapq = int(fields[1]), int(fields[4])
        stats["alignment_records"] += 1
        if flag & 4:
            stats["unmapped_records"] += 1
            continue
        if flag & (256 | 512 | 1024 | 2048):
            stats["excluded_secondary_or_flagged_records"] += 1
            continue
        stats["mapped_primary_alignments_before_filters"] += 1
        operations = re.findall(r"(\d+)([MIDNSHP=X])", fields[5])
        if "".join(n + op for n, op in operations) != fields[5] or fields[9] == "*":
            raise ValueError("缺少 CIGAR 或 reads 序列")
        aligned = sum(int(n) for n, op in operations if op in "MI=X")
        span = sum(int(n) for n, op in operations if op in "MID=X")
        edits = [int(t[5:]) for t in fields[11:] if t.startswith("NM:i:")]
        if not edits or edits[0] < 0:
            raise ValueError("SAM 缺少有效 NM 标签，不能核验 identity")
        if aligned / len(fields[9]) < 0.8 or not span or 1 - edits[0] / span < 0.95:
            stats["excluded_identity_or_coverage"] += 1
            continue
        if mapq < 10 or mapq == 255:
            stats["excluded_mapping_quality"] += 1
            continue
        stats["accepted_read_alignments_all_taxa"] += 1
        ident = gene_id(fields[2])
        if ident in selected:
            if ident not in lengths:
                raise ValueError("SAM缺少目标基因长度")
            counts[ident] += 1
            stats["accepted_read_alignments_target_taxon"] += 1
    return counts, lengths, stats


def quantify(args) -> None:
    manifest = load_manifest(args.manifest)
    if len({(r.assay, r.sample_name) for r in manifest.runs}) != 1:
        raise ValueError("一次定量仅允许一个文库的全部技术 runs；请为DNA和RNA分别准备清单")
    reader = MatouDataReader(args.matou_dir)
    expected = reader.manifest.source_files["gene_ids"].sha256
    if sha256(args.gene_ids) != expected:
        raise ValueError("类群基因全集与已发布 MATOU 基线不符；不能仅用带Pfam的基因")
    selected = set(pl.read_csv(args.gene_ids, separator="\t")["geneID"].to_list())
    index = json.loads((args.index / "index.json").read_text())
    if index["version"] != "read-index-v1":
        raise ValueError("索引版本不支持")
    for name, digest in index["artifacts"].items():
        if Path(name).name != name or sha256(args.index / name) != digest:
            raise ValueError("索引内容已变化")
    job = args.jobs / args.job_id
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}", args.job_id):
        raise ValueError("任务编号无效")
    job.mkdir(parents=True, exist_ok=False)
    versions = {name: tool_version(name) for name in ("fastp", "bowtie2")}
    total_counts, all_lengths, qc = Counter(), None, []
    for run in manifest.runs:
        print(f"processing {run.run_accession}", flush=True)
        files = manifest.sampled_files.get(run.run_accession) or run.files
        raw = [
            args.fastq
            / (f.filename if isinstance(f, SampledReadFile) else Path(urlsplit(f.url).path).name)
            for f in files
        ]
        for path, file in zip(raw, files, strict=True):
            verify_fastq(path, file.size_bytes, file.md5)
        if shutil.disk_usage(job).free < sum(f.size_bytes for f in files) * 2 + 1024**3:
            raise ValueError("质控输出的预留磁盘不足")
        folder = job / run.run_accession
        folder.mkdir()
        clean = [folder / f"clean_{i}.fastq.gz" for i in (1, 2)]
        command = [
            "fastp",
            "-i",
            str(raw[0]),
            "-I",
            str(raw[1]),
            "-o",
            str(clean[0]),
            "-O",
            str(clean[1]),
            "--disable_adapter_trimming",
            "--dont_eval_duplication",
            "--length_required",
            "70",
            "--qualified_quality_phred",
            "20",
            "--thread",
            str(args.threads),
            "--json",
            str(folder / "fastp.json"),
            "--html",
            str(folder / "fastp.html"),
        ]
        checked_command(command, folder / "fastp.log", args.hours)
        alignment = [
            "bowtie2",
            "--very-sensitive",
            "--seed",
            "17",
            "-k",
            "2",
            "-p",
            str(args.threads),
            "-x",
            str(args.index / "catalogue"),
            "-1",
            str(clean[0]),
            "-2",
            str(clean[1]),
        ]
        with (folder / "bowtie2.log").open("x") as log:  # noqa: SIM117
            with subprocess.Popen(
                alignment,
                stdout=subprocess.PIPE,
                stderr=log,
                text=True,
                encoding="utf-8",
                start_new_session=os.name != "nt",
            ) as process:
                timer = threading.Timer(args.hours * 3600, kill_process_tree, args=(process,))
                timer.start()
                try:
                    counts, lengths, statistics = count_sam(process.stdout, selected)
                    code = process.wait(timeout=30)
                    if code:
                        raise ValueError(f"Bowtie2失败或超时：{run.run_accession}，exit={code}")
                except BaseException:
                    kill_process_tree(process)
                    process.wait()
                    raise
                finally:
                    timer.cancel()
        if all_lengths is not None and lengths != all_lengths:
            raise ValueError("不同run的参考长度集合不一致")
        all_lengths = lengths
        total_counts.update(counts)
        report = json.loads((folder / "fastp.json").read_text())
        qc.append(
            {
                "run": run.run_accession,
                "statistics": dict(statistics),
                "before": report["summary"]["before_filtering"],
                "after": report["summary"]["after_filtering"],
                "fastp_command": command,
                "alignment_command": alignment,
                "fastp_report_sha256": sha256(folder / "fastp.json"),
            }
        )
    if not total_counts and index["scope"] == "full_catalogue":
        raise ValueError("没有目标类群的合格比对，不发布空功能谱")
    if index["scope"] == "full_catalogue" and len(all_lengths) != len(selected):
        raise ValueError("标记为完整参考，但没有覆盖类群基因全集；拒绝功能谱比较")
    profile = pl.DataFrame(
        {
            "geneID": list(total_counts),
            "value": [count / all_lengths[ident] for ident, count in total_counts.items()],
        },
        schema={"geneID": pl.Int64, "value": pl.Float64},
    )
    profile.write_parquet(job / "profile.parquet")
    write_json_new(job / "input.json", manifest.model_dump(mode="json"))
    assay, sample = manifest.runs[0].assay, manifest.runs[0].sample_name
    reader.sample_artifact(assay, sample)
    write_json_new(
        job / "result.json",
        {
            "version": "read-quantification-v1",
            "created_at": datetime.now(UTC).isoformat(),
            "assay": assay,
            "sample_name": sample,
            "taxon": reader.manifest.selection["taxon"],
            "runs": [r.run_accession for r in manifest.runs],
            "matou_manifest_sha256": reader.manifest_record.sha256,
            "reference": index,
            "qc": qc,
            "method": {
                "version": "read-sensitivity-v1",
                "tools": versions,
                "sampling": "head_pairs_not_random"
                if manifest.head_pairs_per_run
                else "all_run_reads",
                "head_pairs_per_run": manifest.head_pairs_per_run,
                "archive_md5_verified": manifest.head_pairs_per_run is None,
                "value": "accepted_read_count/gene_length_bp; not TPM or published RPKM",
                "min_mapq": 10,
                "min_identity": 0.95,
                "min_query_coverage": 0.8,
                "multi_mapping": "secondary excluded; primary MAPQ>=10; no fractional allocation",
                "rna": "no additional rRNA depletion; archive preprocessing stage not assumed",
                "duplicate_removal": "not performed; not an author-pipeline reproduction",
                "adapter_trimming": "disabled_until_library_adapters_verified",
                "duplication_evaluation": "disabled_to_bound_memory; not deduplication",
                "reference_taxon_genes_present": len(all_lengths),
                "taxon_gene_count": len(selected),
            },
            "artifacts": {f: sha256(job / f) for f in ("input.json", "profile.parquet")},
        },
    )
    print(f"completed {args.job_id}", flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    plan = sub.add_parser("plan")
    plan.add_argument("--supplement", type=Path, required=True)
    plan.add_argument("--samples", nargs="+", required=True)
    plan.add_argument("--output", type=Path, required=True)
    fetch = sub.add_parser("download")
    fetch.add_argument("--manifest", type=Path, required=True)
    fetch.add_argument("--directory", type=Path, required=True)
    fetch.add_argument("--max-gb", type=float, default=20)
    sample = sub.add_parser("sample")
    sample.add_argument("--manifest", type=Path, required=True)
    sample.add_argument("--directory", type=Path, required=True)
    sample.add_argument("--pairs", type=int, default=100000)
    sample.add_argument("--output", type=Path, required=True)
    index = sub.add_parser("index")
    index.add_argument("--reference", type=Path, required=True)
    index.add_argument("--output", type=Path, required=True)
    index.add_argument("--scope", choices=["full_catalogue", "candidate_subset"], required=True)
    reference = sub.add_parser("reference")
    reference.add_argument("--matou-dir", type=Path, required=True)
    reference.add_argument("--pfam", required=True)
    reference.add_argument("--output", type=Path, required=True)
    run = sub.add_parser("quantify")
    for name in ("manifest", "fastq", "index", "matou-dir", "gene-ids", "jobs"):
        run.add_argument("--" + name, type=Path, required=True)
    run.add_argument("--job-id", required=True)
    for command in (index, run):
        command.add_argument("--threads", type=int, choices=range(1, 17), default=4)
        command.add_argument("--hours", type=float, default=24)
    args = parser.parse_args()
    if hasattr(args, "hours") and not 0 < args.hours <= 168:
        parser.error("hours must be in (0, 168]")
    if args.command == "plan":
        manifest = plan_reads(args.supplement, args.samples)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        write_json_new(args.output, manifest.model_dump(mode="json"))
        size = sum(f.size_bytes for r in manifest.runs for f in r.files)
        print(f"{len(manifest.runs)} runs; {size / 1024**3:.2f} GiB; {args.output}")
    elif args.command == "download":
        if not 0 < args.max_gb <= 200:
            parser.error("pilot max-gb must be in (0, 200]")
        download(load_manifest(args.manifest), args.directory, args.max_gb)
    elif args.command == "index":
        build_index(args.reference, args.output, args.scope, args.threads, args.hours)
    elif args.command == "sample":
        result = sample_reads(load_manifest(args.manifest), args.directory, args.pairs)
        write_json_new(args.output, result.model_dump(mode="json"))
    elif args.command == "reference":
        export_reference(args.matou_dir, args.pfam, args.output)
    else:
        quantify(args)


if __name__ == "__main__":
    main()
