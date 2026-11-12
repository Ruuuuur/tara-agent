"""标准输入输出 MCP 入口；路径仅由本机维护者配置，不作为模型工具开放。"""

import argparse
from pathlib import Path

from tara_agent.config import get_settings
from tara_agent.data.matou_reader import MatouDataReader
from tara_agent.data.reader import ProcessedDataError, ProcessedDataReader
from tara_agent.mcp.server import create_server


def main() -> None:
    parser = argparse.ArgumentParser(description="Read-only Tara Oceans MCP server (stdio).")
    parser.add_argument("--processed-data-dir", type=Path, help="Prepared core data directory.")
    optional = parser.add_mutually_exclusive_group()
    optional.add_argument("--matou-data-dir", type=Path, help="Prepared MATOU data directory.")
    optional.add_argument(
        "--core-only", action="store_true", help="Expose only the seven core tools."
    )
    args = parser.parse_args()
    try:
        settings = get_settings()
        reader = ProcessedDataReader(args.processed_data_dir or settings.processed_data_dir)
        matou_dir = None if args.core_only else (args.matou_data_dir or settings.matou_data_dir)
        matou = MatouDataReader(matou_dir) if matou_dir is not None else None
        server = create_server(
            reader,
            matou_reader=matou,
            read_jobs_dir=None if args.core_only else settings.read_jobs_dir,
        )
    except (OSError, ValueError, ProcessedDataError) as error:
        # 启动诊断走 stderr，stdout 只允许 MCP 协议消息。
        parser.exit(
            2, f"Tara MCP startup failed: {error}\nCheck the prepared data paths and manifests.\n"
        )
    server.run(transport="stdio")
