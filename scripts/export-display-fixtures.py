"""采集运行期固定状态与错误文案；不执行源码、条件或科学计算。"""

import argparse
import ast
import json
import runpy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LITERALS = runpy.run_path(str(ROOT / "scripts/export-warning-fixtures.py"))[
    "literal_variants"
]
TARGET = ROOT / "frontend/tests/fixtures/backend-display-messages.json"


def collect(source_dir=None):
    source = source_dir or ROOT / "backend/src/tara_agent"
    found = set()
    for path in source.rglob("*.py"):
        # 离线准备、模型契约校验和开发配置不属于网页运行期显示入口。
        relative = path.relative_to(source)
        if relative.parts[0] not in {
            "agent",
            "analysis",
            "api",
            "data_service",
            "mcp",
            "data",
        }:
            continue
        if path.name.endswith(
            ("_prepare.py", "_models.py", "_cli.py")
        ) or path.name in {
            "config.py",
            "prompts.py",
            "resources.py",
            "models.py",
            "multistep.py",
            "workflow.py",
        }:
            continue
        if relative.parts[0] == "data" and path.stem not in {
            "reader",
            "matou_reader",
            "matou_study",
            "research_context",
            "function_reference",
        }:
            continue
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            pairs = []
            if isinstance(node, ast.keyword) and node.arg in {
                "reason",
                "output",
                "detail",
                "title",
                "x_label",
                "y_label",
                "name",
            }:
                pairs.append(("title" if node.arg == "name" else node.arg, node.value))
            elif isinstance(node, ast.Dict):
                pairs.extend(
                    (key.value, value)
                    for key, value in zip(node.keys, node.values)
                    if isinstance(key, ast.Constant)
                    and key.value in {"reason", "output"}
                )
            elif isinstance(node, ast.Assign):
                pairs.extend(
                    (target.id, node.value)
                    for target in node.targets
                    if isinstance(target, ast.Name) and target.id == "reason"
                )
            elif (
                isinstance(node, ast.Raise)
                and isinstance(node.exc, ast.Call)
                and node.exc.args
            ):
                pairs.append(("error", node.exc.args[0]))
            elif (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == "section"
                and len(node.args) > 2
            ):
                pairs.append(("reason", node.args[2]))
            # frame 的资料键为字面量时，覆盖读取器固定前缀与资料键拼成的失败原因。
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "frame"
                and isinstance(node.func.value, ast.Attribute)
                and node.func.value.attr == "research"
                and node.args
                and isinstance(node.args[0], ast.Constant)
                and isinstance(node.args[0].value, str)
            ):
                found.add(("reason", "未准备研究资料：" + node.args[0].value))
            for kind, expression in pairs:
                for text in LITERALS(expression) or ():
                    if any("\u3400" <= char <= "\u9fff" for char in text):
                        found.add((kind, text))
    return [{"kind": kind, "text": text} for kind, text in sorted(found)]


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    expected = json.dumps(collect(), ensure_ascii=False, indent=2) + "\n"
    if args.check:
        if TARGET.read_text(encoding="utf-8") != expected:
            raise SystemExit(
                "显示文案目录已过期：运行 python3 scripts/export-display-fixtures.py 并补齐翻译"
            )
        print("Backend display fixture is current")
    else:
        TARGET.write_text(expected, encoding="utf-8")
