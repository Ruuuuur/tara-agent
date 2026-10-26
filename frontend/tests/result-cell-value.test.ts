import { strict as assert } from "node:assert";
import { test } from "node:test";
import { resultCellValue } from "../src/lib/result-cell-value";

test("saved LHC model and section display use English while retaining original rows", () => {
  const rows = [
    { target: "LHC亚家族", sample_count: 246 },
    { output: "LHC亚家族环境关联", status: "completed" },
    { reason: "水层或实验协议不在当前方法范围", sample_id: "TARA_001" },
  ];
  const saved = structuredClone(rows);
  assert.equal(resultCellValue("target", rows[0], "en"), "LHC subfamilies");
  assert.equal(resultCellValue("output", rows[1], "en"), "LHC subfamily environmental associations");
  assert.match(String(resultCellValue("reason", rows[2], "en")), /depth layer or experimental protocol.*outside the scope/);
  for (const row of rows) for (const column of Object.keys(row)) {
    assert.equal(resultCellValue(column, row, "zh"), row[column as keyof typeof row]);
  }
  assert.deepEqual(rows, saved);
});

test("PLS blocked reason preserves the distinction between missing subfamily profiles and insufficient observations", () => {
  const reason = "需要以作者逐geneID亚家族注释与当前MetaG/MetaT基因信号预计算的lhc_profiles；PF00504总量不能代替LHCf/LHCq/LHCr/LHCx/LHCz。作者公开Pfam汇总表不能还原亚家族。";
  const text = String(resultCellValue("reason", {reason}, "en"));
  assert.match(text, /lhc_profiles must be precomputed/);
  assert.match(text, /PF00504 signal cannot substitute for LHCf\/LHCq\/LHCr\/LHCx\/LHCz/);
  assert.match(text, /public Pfam summary tables cannot reconstruct subfamilies/);
  assert.match(String(resultCellValue("reason", {reason: "完整观测不足4组，无法稳定提取两个成分"}, "en")), /Fewer than four complete groups.*two components/);
});

test("unknown diagnostics, scientific labels and numbers retain their original values", () => {
  for (const column of ["target", "output", "reason", "function_name", "sample_count", "constructor"]) {
    for (const value of ["未知科学诊断", "LHC亚家族 additional detail", "constructor", "toString", 246, null]) {
      assert.equal(resultCellValue(column, { [column]: value }, "en"), value);
    }
  }
  assert.equal(resultCellValue("function_name", {function_name: "LHC亚家族"}, "en"), "LHC亚家族");
  const row = {taxon_label: "未鉴定到属（Root;Eukaryota）", classification_status: "unresolved"};
  assert.equal(resultCellValue("taxon_label", row, "en"), "Unresolved genus (Root;Eukaryota)");
});

test("community PLS targets and iteration-limit reasons use complete templates", () => {
  for (const marker of ["v4", "v9"]) {
    assert.equal(resultCellValue("target", {target: marker + "群落"}, "en"), marker.toUpperCase() + " community");
  }
  const reason = "NMDS在250次迭代预算内未收敛";
  assert.equal(resultCellValue("reason", {reason}, "en"), "NMDS did not converge within the budget of 250 iterations.");
  assert.equal(resultCellValue("reason", {reason}, "zh"), reason);
});
