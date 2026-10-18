import { strict as assert } from "node:assert";
import { test } from "node:test";
import { translateLabel } from "../src/lib/i18n";

// 使用截图中八个完整标题，覆盖步骤、结果角色、复用图和表后缀的组合。
const screenshotTitles = [
  ["步骤 1 · 本次返回样本的分类群相对丰度", "Step 1 · Taxon relative abundance in returned samples"],
  ["步骤 4 · 本次返回样本的分类群相对丰度", "Step 4 · Taxon relative abundance in returned samples"],
  ["步骤 1 · 【中间步骤结果】样本类群相对丰度表", "Step 1 · [Intermediate result] Taxon relative abundance per sample table"],
  ["步骤 2 · 【中间步骤结果】样本采集与环境信息表", "Step 2 · [Intermediate result] Sample collection and environmental information"],
  ["步骤 3 · 【中间步骤结果】样本类群相对丰度表", "Step 3 · [Intermediate result] Taxon relative abundance per sample table"],
  ["步骤 3 · 【中间步骤结果】样本内分类组成表", "Step 3 · [Intermediate result] Within-sample taxonomic composition table"],
  ["步骤 3 · 【中间步骤结果】样本组成与优势类群摘要表", "Step 3 · [Intermediate result] Sample composition and dominant taxa table"],
  ["步骤 4 · 【中间步骤结果】样本类群相对丰度表", "Step 4 · [Intermediate result] Taxon relative abundance per sample table"],
];
for (const [source, expected] of screenshotTitles) {
  test(`complete English artifact title: ${source}`, () => {
    assert.equal(translateLabel(source, "en"), expected);
    assert.doesNotMatch(translateLabel(source, "en"), /[\u3400-\u9fff]/);
    assert.equal(translateLabel(source, "zh"), source);
    assert.equal(translateLabel(expected, "en"), expected);
  });
}

test("dynamic identifiers and scientific values survive translated title wrappers", () => {
  assert.equal(translateLabel("步骤 12 · 【最终结果】TARA_A100000038 / V9 / Opisthokonta / Shannon 2.5", "en"), "Step 12 · [Final result] TARA_A100000038 / V9 / Opisthokonta / Shannon 2.5");
  assert.equal(translateLabel("PF00069 采样编码对应的相对功能信号", "en"), "Relative functional signal for matched sampling codes: PF00069");
});

test("existing exact table titles keep their established translation", () => {
  assert.equal(translateLabel("PLS计算条件与完成状态表", "en"), "PLS settings and completion status");
  assert.equal(translateLabel("temperature 与相对丰度", "en"), "temperature vs relative abundance");
});
