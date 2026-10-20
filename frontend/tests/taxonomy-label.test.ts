import { strict as assert } from "node:assert";
import { test } from "node:test";
import { taxonomyCellValue } from "../src/lib/taxonomy-label";

const path = "Root;Eukaryota;Stramenopiles;Ochrophyta;Bacillariophyta;unclassified_X";
for (const [rank, english] of [["属", "genus"], ["种", "species"]]) {
  test(`unresolved ${english} display preserves full source path and stored value`, () => {
    const row = { taxon_label: `未鉴定到${rank}（${path}）`, classification_status: "unresolved", taxonomy: path, read_count: 36374 };
    const saved = structuredClone(row);
    assert.equal(taxonomyCellValue("taxon_label", row, "en"), `Unresolved ${english} (${path})`);
    assert.equal(taxonomyCellValue("taxon_label", row, "zh"), saved.taxon_label);
    assert.equal(taxonomyCellValue("taxonomy", row, "en"), path);
    assert.equal(taxonomyCellValue("read_count", row, "en"), 36374);
    assert.deepEqual(row, saved);
  });
}

test("assigned names, unknown diagnostics and other fields are never translated", () => {
  for (const value of ["Trieres", "原始分类名", "未鉴定到属（path） additional detail", "未鉴定到科（path）", null]) {
    const row = { taxon_label: value, classification_status: "unresolved" };
    assert.equal(taxonomyCellValue("taxon_label", row, "en"), value);
  }
  const row = { taxon_label: `未鉴定到属（${path}）`, classification_status: "assigned" };
  assert.equal(taxonomyCellValue("taxon_label", row, "en"), row.taxon_label);
});
