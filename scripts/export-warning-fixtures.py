"""采集后端固定中文警告，防止新提示遗漏英文界面回归。"""
import argparse
import ast
import json
from pathlib import Path

root = Path(__file__).resolve().parents[1]
target = root / "frontend/tests/fixtures/backend-warning-messages.json"

def collect():
    found = set()
    for path in (root / "backend/src").rglob("*.py"):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if not isinstance(node, ast.Call):
                continue
            keywords = {item.arg: item.value for item in node.keywords}
            code, message = keywords.get("code"), keywords.get("message")
            if not (isinstance(code, ast.Constant) and isinstance(code.value, str)
                    and isinstance(message, ast.Constant) and isinstance(message.value, str)):
                continue
            if any("\u3400" <= character <= "\u9fff" for character in message.value):
                found.add((code.value, message.value))
    return [{"code": code, "message": message} for code, message in sorted(found)]

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="仅检查目录是否与后端一致")
    args = parser.parse_args()
    expected = json.dumps(collect(), ensure_ascii=False, indent=2) + "\n"
    if args.check:
        if target.read_text(encoding="utf-8") != expected:
            raise SystemExit("固定提示目录已过期：运行 python3 scripts/export-warning-fixtures.py 更新后补齐翻译")
        print("Backend warning fixture is current")
    else:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(expected, encoding="utf-8")
