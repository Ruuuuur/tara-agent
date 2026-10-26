"""固定提示目录覆盖条件拼接，不执行代码或改写动态科学诊断。"""

import runpy
from pathlib import Path

EXPORTER = Path(__file__).resolve().parents[2] / "scripts/export-warning-fixtures.py"
collect = runpy.run_path(str(EXPORTER))["collect"]


def test_collects_both_conditional_messages_without_executing_the_condition(tmp_path):
    (tmp_path / "warnings.py").write_text(
        "ResultWarning(code='method', message='说明：' + "
        "('全部信号' if must_not_execute() else '保留功能'))\n"
        "ResultWarning(code='diagnostic', message='未知样本：' + sample_id)\n",
        encoding="utf-8",
    )
    assert collect(tmp_path) == [
        {"code": "method", "message": "说明：保留功能"},
        {"code": "method", "message": "说明：全部信号"},
    ]


def test_current_backend_catalog_includes_both_normalization_branches():
    notes = [item for item in collect() if item["code"] == "paper_denominator_difference"]
    assert len(notes) == 2
    assert any("保留功能不再二次归一化" in item["message"] for item in notes)
    assert any("当前榜单按作者脚本二次归一化" in item["message"] for item in notes)
