"""从本地作者文件建立论文参考资料包；可选下载固定版本的公开文件。"""

import argparse
from pathlib import Path
from tempfile import TemporaryDirectory

import httpx

from tara_agent.data.function_reference import AUTHOR_COMMIT, FunctionReference, prepare_reference
from tara_agent.data.matou_reader import MatouDataReader

FILES = [
    "scripts/contextual_data/PfamA.list",
    "scripts/contextual_data/station_ocean.tsv",
    "scripts/contextual_data/physicochemistry.for.metaT.tsv",
    "scripts/contextual_data/station_Lat_Long_uniq.withTaraPrefix.tsv",
    "datasets/Pfam_sums/metaG/Bacillariophyta.MATOU-v1.5.Pfam.metaG.tsv.gz",
    "datasets/Pfam_sums/metaT/Bacillariophyta.MATOU-v1.5.Pfam.metaT.tsv.gz",
    "datasets/LHC/LHC.diatoms.MATOUv1.5.seqs.function.tsv.gz",
]


def validate_bundle(directory: Path, matou_dir: Path | None) -> None:
    reference = FunctionReference(directory)
    reference.validate()
    if matou_dir is not None and "lhc_profiles" in reference.manifest["files"]:
        reader = MatouDataReader(matou_dir)
        if reference.manifest.get("lhc_source_manifest_sha256") != reader.manifest_record.sha256:
            raise ValueError("LHC亚家族预计算与当前MATOU版本不一致；请在新目录重新准备资料")


def download_sources(directory: Path) -> None:
    directory.mkdir(parents=True, exist_ok=False)
    with httpx.Client(timeout=120, follow_redirects=True) as client:
        for name in FILES:
            url = f"https://raw.githubusercontent.com/JJPierellaKarlusich/Diatom_patters/{AUTHOR_COMMIT}/metaT/{name}"
            with client.stream("GET", url) as response:
                response.raise_for_status()
                total = 0
                with (directory / Path(name).name).open("xb") as stream:
                    for block in response.iter_bytes():
                        total += len(block)
                        if total > 128 * 1024 * 1024:
                            raise ValueError("参考文件超过128MiB保护上限")
                        stream.write(block)
            print(Path(name).name, flush=True)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-dir", type=Path, help="已下载的作者文件；--download时可省略")
    parser.add_argument("--output-dir", type=Path, help="默认写入 --matou-dir/paper_task2")
    parser.add_argument("--download", action="store_true")
    parser.add_argument(
        "--check", action="store_true", help="只核验已有资料及LHC版本，不下载或写入"
    )
    parser.add_argument(
        "--matou-dir",
        type=Path,
        help="可选：用当前MATOU逐基因数据预计算LHC亚家族；仅在独立准备阶段扫描",
    )
    args = parser.parse_args(argv)
    if args.output_dir is None:
        if args.matou_dir is None:
            parser.error("需要 --matou-dir 或 --output-dir")
        args.output_dir = args.matou_dir / "paper_task2"
    if args.check and args.download:
        parser.error("--check不能与--download同时使用")
    try:
        if args.output_dir.exists() or args.check:
            validate_bundle(args.output_dir, args.matou_dir)
            print(f"资料核验通过，复用已有文件：{args.output_dir / 'manifest.json'}")
            return
        if args.source_dir is None and not args.download:
            parser.error("准备新资料需要 --source-dir 或 --download")
        args.output_dir.parent.mkdir(parents=True, exist_ok=True)
        # 全部转换、摘要与LHC版本检查成功后才发布，失败不留下可被误用的半成品。
        with TemporaryDirectory(prefix=".function-reference-", dir=args.output_dir.parent) as work:
            workspace = Path(work)
            source = args.source_dir or workspace / "sources"
            if args.download:
                download_sources(source)
            prepared = workspace / "prepared"
            prepare_reference(source, prepared, matou_dir=args.matou_dir)
            validate_bundle(prepared, args.matou_dir)
            if args.output_dir.exists():
                raise ValueError("输出目录已由其他进程创建，不覆盖")
            prepared.rename(args.output_dir)
        print(
            f"资料准备完成，请重启实际执行计算的后端或数据服务：{args.output_dir / 'manifest.json'}"
        )
    except (OSError, ValueError, KeyError, httpx.HTTPError) as error:
        parser.error(f"参考资料未就绪：{error}；已有目录不会覆盖，请检查挂载或使用新输出目录")


if __name__ == "__main__":
    main()
