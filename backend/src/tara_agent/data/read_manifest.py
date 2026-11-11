"""从作者的明确 run 对照与 ENA 记录生成下载清单；不按名称猜测样本。"""

import hashlib
import json
import re
import urllib.request
import xml.etree.ElementTree as ET
import zipfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal
from urllib.parse import urlencode, urlsplit

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ReadFile(BaseModel):
    model_config = ConfigDict(extra="forbid")
    url: str
    size_bytes: int = Field(gt=0)
    md5: str = Field(pattern=r"^[0-9a-f]{32}$")

    @model_validator(mode="after")
    def ena_only(self):
        parsed = urlsplit(self.url)
        if (
            parsed.scheme != "https"
            or parsed.hostname != "ftp.sra.ebi.ac.uk"
            or parsed.username
            or parsed.password
            or parsed.query
            or parsed.fragment
            or not re.fullmatch(r"/vol1/fastq/[A-Za-z0-9_./-]+\.fastq\.gz", parsed.path)
            or ".." in parsed.path
        ):
            raise ValueError("只允许 ENA 官方 HTTPS FASTQ 地址")
        return self


class ReadRun(BaseModel):
    model_config = ConfigDict(extra="forbid")
    run_accession: str = Field(pattern=r"^ERR[0-9]+$")
    study_accession: str
    experiment_accession: str
    biosample: str
    sample_name: str = Field(pattern=r"^[A-Za-z0-9_-]{1,100}$")
    sample_id: str
    assay: Literal["MetaG", "MetaT"]
    library_source: str
    files: list[ReadFile] = Field(min_length=2, max_length=2)
    evidence_row: int = Field(ge=3)


class SampledReadFile(BaseModel):
    model_config = ConfigDict(extra="forbid")
    filename: str = Field(pattern=r"^ERR[0-9]+_[12]\.sample\.fastq\.gz$")
    size_bytes: int = Field(gt=0)
    md5: str = Field(pattern=r"^[0-9a-f]{32}$")
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class ReadManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    version: Literal["ena-matou-pilot-v1"] = "ena-matou-pilot-v1"
    created_at: str
    source: str = "https://doi.org/10.1038/s41467-017-02342-1; Supplementary Data 8"
    source_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    runs: list[ReadRun] = Field(min_length=1, max_length=100)
    head_pairs_per_run: int | None = Field(default=None, ge=1, le=1000000)
    sampled_files: dict[str, list[SampledReadFile]] = Field(default_factory=dict)

    @model_validator(mode="after")
    def unique_runs(self):
        if len({r.run_accession for r in self.runs}) != len(self.runs):
            raise ValueError("run 不能重复或绑定多个 MATOU 样本")
        urls = [f.url for r in self.runs for f in r.files]
        if len(set(urls)) != len(urls):
            raise ValueError("FASTQ 地址不能重复")
        if self.head_pairs_per_run is None and self.sampled_files:
            raise ValueError("缺少抽样定义")
        if self.head_pairs_per_run is not None:
            if set(self.sampled_files) != {r.run_accession for r in self.runs}:
                raise ValueError("抽样文件必须覆盖清单全部runs")
            for run, files in self.sampled_files.items():
                if [f.filename for f in files] != [f"{run}_{i}.sample.fastq.gz" for i in (1, 2)]:
                    raise ValueError("抽样的两端文件身份不一致")
        return self


def sha256(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def write_json_new(path: Path, value: dict) -> None:
    """不覆盖既有产物；中断留下的临时文件不会被网页读取。"""
    if path.exists():
        raise ValueError(f"目标已存在，请使用新的目录：{path.name}")
    temporary = path.with_suffix(path.suffix + ".partial")
    with temporary.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
    temporary.rename(path)


def supplementary_rows(path: Path) -> list[dict]:
    ns = {"x": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    with zipfile.ZipFile(path) as archive:
        strings = [
            "".join(e.itertext())
            for e in ET.fromstring(archive.read("xl/sharedStrings.xml")).findall("x:si", ns)
        ]
        sheet = ET.fromstring(archive.read("xl/worksheets/sheet1.xml"))
        rows = []
        for row in sheet.findall(".//x:row", ns)[2:]:
            values = {}
            for cell in row:
                value = cell.find("x:v", ns)
                text = "" if value is None else value.text or ""
                values[re.sub(r"[0-9]", "", cell.attrib["r"])] = (
                    strings[int(text)] if cell.attrib.get("t") == "s" and text else text
                )
            if values.get("N"):
                rows.append({**values, "row": int(row.attrib["r"])})
        return rows


def ena_run(accession: str) -> dict:
    if not re.fullmatch(r"ERR[0-9]+", accession):
        raise ValueError("作者表中的 run 编号无效")
    fields = (
        "run_accession,study_accession,sample_accession,experiment_accession,"
        "library_source,library_layout,fastq_ftp,fastq_bytes,fastq_md5"
    )
    url = "https://www.ebi.ac.uk/ena/portal/api/filereport?" + urlencode(
        {"accession": accession, "result": "read_run", "fields": fields, "format": "json"}
    )
    with urllib.request.urlopen(url, timeout=45) as response:
        rows = json.load(response)
    if len(rows) != 1 or rows[0]["run_accession"] != accession:
        raise ValueError(f"ENA 未返回唯一 run：{accession}")
    return rows[0]


def plan_reads(source: Path, sample_names: list[str]) -> ReadManifest:
    if not sample_names or len(set(sample_names)) != len(sample_names):
        raise ValueError("必须提供不重复的 MATOU 样本编码")
    rows = supplementary_rows(source)
    selected = [row for row in rows if row["N"] in sample_names]
    if len(selected) != len(sample_names):
        raise ValueError("样本未唯一出现在 Supplementary Data 8，拒绝猜测扩展样本映射")
    runs = []
    for row in selected:
        accessions = re.findall(r"ERR[0-9]+", row.get("L", ""))
        if not accessions:
            raise ValueError(f"作者资料缺少 run：{row['N']}")
        for accession in accessions:
            record = ena_run(accession)
            allowed = {"MetaG": {"METAGENOMIC"}, "MetaT": {"METATRANSCRIPTOMIC", "TRANSCRIPTOMIC"}}
            if (
                record["sample_accession"] != row["B"]
                or record["library_layout"] != "PAIRED"
                or record["library_source"] not in allowed.get(row["C"], set())
            ):
                raise ValueError(f"ENA 身份、实验类型或双端布局与作者资料不符：{accession}")
            urls = record["fastq_ftp"].split(";")
            sizes = record["fastq_bytes"].split(";")
            hashes = record["fastq_md5"].split(";")
            if not (len(urls) == len(sizes) == len(hashes) == 2):
                raise ValueError(f"首版仅接受明确的两端 FASTQ：{accession}")
            files = [
                ReadFile(url="https://" + u, size_bytes=int(n), md5=h)
                for u, n, h in zip(urls, sizes, hashes, strict=True)
            ]
            if not (
                urlsplit(files[0].url).path.endswith(f"/{accession}_1.fastq.gz")
                and urlsplit(files[1].url).path.endswith(f"/{accession}_2.fastq.gz")
            ):
                raise ValueError("FASTQ 端序不明确，需人工核验")
            runs.append(
                ReadRun(
                    run_accession=accession,
                    study_accession=record["study_accession"],
                    experiment_accession=record["experiment_accession"],
                    biosample=row["B"],
                    sample_name=row["N"],
                    sample_id=row["A"],
                    assay=row["C"],
                    library_source=record["library_source"],
                    files=files,
                    evidence_row=row["row"],
                )
            )
    return ReadManifest(
        created_at=datetime.now(UTC).isoformat(), source_sha256=sha256(source), runs=runs
    )
