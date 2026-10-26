"""显示目录覆盖真实字段路径，不执行代码或采集任意科学数据。"""

import runpy
from pathlib import Path

COLLECT = runpy.run_path(
    str(Path(__file__).resolve().parents[2] / "scripts/export-display-fixtures.py")
)["collect"]


def test_display_export_covers_dict_assignment_and_section_reason_paths(tmp_path):
    source = tmp_path / "analysis"
    source.mkdir()
    (source / "sample.py").write_text(
        "reason = '缺少映射'\n"
        "self.research.frame('environment')\n"
        "rows = [{'reason': '常量变量'}]\n"
        "section('association', False, '无样本')\n"
        "raise ValueError('输入' + ('无效' if must_not_run() else '缺失'))\n"
        "rows.append({'reason': '未知样本：' + raw_id})\n",
        encoding="utf-8",
    )
    assert COLLECT(tmp_path) == [
        {"kind": "error", "text": "输入无效"},
        {"kind": "error", "text": "输入缺失"},
        {"kind": "reason", "text": "常量变量"},
        {"kind": "reason", "text": "无样本"},
        {"kind": "reason", "text": "未准备研究资料：environment"},
        {"kind": "reason", "text": "缺少映射"},
    ]


def test_checked_in_display_catalog_tracks_current_runtime_sources():
    import json

    root = Path(__file__).resolve().parents[2]
    expected = json.loads(
        (root / "frontend/tests/fixtures/backend-display-messages.json").read_text()
    )
    assert COLLECT() == expected
