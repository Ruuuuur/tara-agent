"""维护者离线管理访问令牌；服务端只保存摘要，撤销对后续请求立即生效。"""

import argparse
import hashlib
import json
import os
import re
import secrets
import time
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field


class TokenRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")
    client_id: str = Field(pattern=r"^[a-zA-Z0-9_-]{1,64}$")
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    expires_at: int = Field(gt=0)


class TokenRegistry(BaseModel):
    model_config = ConfigDict(extra="forbid")
    tokens: list[TokenRecord] = Field(max_length=1000)


def load_registry(path: Path) -> TokenRegistry:
    registry = TokenRegistry.model_validate_json(path.read_bytes())
    ids = [item.client_id for item in registry.tokens]
    hashes = [item.sha256 for item in registry.tokens]
    if len(set(ids)) != len(ids) or len(set(hashes)) != len(hashes):
        raise ValueError("Duplicate token identity")
    return registry


def main() -> None:
    parser = argparse.ArgumentParser(description="Manage Tara MCP bearer tokens (offline admin).")
    parser.add_argument("--registry", type=Path, required=True)
    sub = parser.add_subparsers(dest="action", required=True)
    create = sub.add_parser("create")
    create.add_argument("client_id")
    create.add_argument("--output", type=Path, required=True)
    create.add_argument("--days", type=int, default=90)
    revoke = sub.add_parser("revoke")
    revoke.add_argument("client_id")
    args = parser.parse_args()
    if not re.fullmatch(r"[a-zA-Z0-9_-]{1,64}", args.client_id):
        parser.error("client_id must be 1–64 letters, digits, underscores or hyphens")
    registry = load_registry(args.registry) if args.registry.exists() else TokenRegistry(tokens=[])
    if args.action == "create":
        if not 1 <= args.days <= 365:
            parser.error("days must be between 1 and 365")
        if any(item.client_id == args.client_id for item in registry.tokens):
            parser.error("client_id already exists; revoke it before rotation")
        token = secrets.token_urlsafe(32)
        registry.tokens.append(
            TokenRecord(
                client_id=args.client_id,
                sha256=hashlib.sha256(token.encode()).hexdigest(),
                expires_at=int(time.time()) + args.days * 86400,
            )
        )
        # 排他创建防止覆盖维护者已有凭据；令牌绝不输出到日志或终端。
        with open(args.output, "x", opener=lambda p, f: os.open(p, f, 0o600)) as stream:
            stream.write(token + "\n")
    else:
        if not any(item.client_id == args.client_id for item in registry.tokens):
            parser.error("client_id not found")
        registry.tokens = [item for item in registry.tokens if item.client_id != args.client_id]
    temporary = args.registry.with_name(args.registry.name + ".tmp")
    with open(temporary, "x", opener=lambda p, f: os.open(p, f, 0o600)) as stream:
        stream.write(registry.model_dump_json(indent=2) + "\n")
    temporary.replace(args.registry)
    print(
        json.dumps(
            {"action": args.action, "client_id": args.client_id, "registry": str(args.registry)}
        )
    )


if __name__ == "__main__":
    main()
