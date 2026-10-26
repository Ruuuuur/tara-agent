import { strict as assert } from "node:assert";
import { test } from "node:test";
import { warningMessage } from "../src/lib/warning-message";
import backendWarnings from "./fixtures/backend-warning-messages.json";

const method = {
  code: "unrarefied_diversity",
  message: "观测丰富度和 Shannon 指数基于未经稀释抽样的测序读数计算，测序量差异可能影响样本间比较。",
};
const partial = {
  code: "analysis_incomplete",
  message: "下一步规划未完成，已停止并保留已完成结果：模型返回了无效的分析决定",
};

test("screenshot method note preserves the scientific caveat in English", () => {
  assert.equal(warningMessage(method, "en"), "Observed richness and the Shannon index are calculated from unrarefied sequencing read counts. Differences in sequencing depth may affect comparisons between samples.");
});
test("screenshot partial result explains both the stop and its actual cause", () => {
  assert.equal(warningMessage(partial, "en"), "Planning the next step did not complete. Analysis stopped and completed results were retained: The model returned an invalid analysis decision.");
});
test("saved notes switch display language without mutating the stored warning", () => {
  for (const warning of [method, partial]) {
    const original = { ...warning };
    assert.doesNotMatch(warningMessage(warning, "en"), /[\u3400-\u9fff]/);
    assert.equal(warningMessage(warning, "zh"), original.message);
    assert.deepEqual(warning, original);
  }
});
test("unknown scientific text, warning codes and identifiers are preserved", () => {
  const unknown = { code: "new_method", message: "样本 TARA_A100000038：Shannon=2.5，n=12。" };
  assert.equal(warningMessage(unknown, "en"), unknown.message);
  assert.equal(warningMessage({ ...method, code: "new_method" }, "en"), method.message);
  assert.equal(warningMessage({ ...method, message: method.message + " TARA_A100000038" }, "en"), method.message + " TARA_A100000038");
});
test("unknown failure details are kept verbatim after the translated stop notice", () => {
  const detail = "missing field station_id for TARA_A100000038; n=12";
  assert.equal(warningMessage({ code: "analysis_incomplete", message: "步骤未完成，已停止且不自动重试：" + detail }, "en"), "The step did not complete. Analysis stopped without an automatic retry: " + detail);
});
test("budget stops continue to report partial completion", () => {
  assert.equal(warningMessage({ code: "analysis_incomplete", message: "工具调用预算已用尽；保留已完成结果。" }, "en"), "The tool call limit was reached. Completed results have been retained.");
});

test("unrecognized stop messages are not treated as dictionary entries", () => {
  for (const message of ["constructor", "toString", "__proto__"]) {
    assert.equal(warningMessage({ code: "analysis_incomplete", message }, "en"), message);
  }
});


test("read-count metric note translates both deployed service wordings and preserves unknown details", () => {
  const code = "read_count_is_not_cell_abundance";
  const screenshot = "测序读数是测序观测信号，不能直接解释为细胞丰度。";
  const legacy = "原始测序读数及据此计算的相对丰度属于测序信号，不是对细胞丰度的直接测量。";
  assert.equal(warningMessage({ code, message: screenshot }, "en"), "Sequencing read counts are sequencing observations and cannot be interpreted directly as cell abundance.");
  assert.equal(warningMessage({ code, message: legacy }, "en"), "Raw read counts and the relative abundances calculated from them represent sequencing signals, not direct measurements of cell abundance.");
  assert.equal(warningMessage({ code, message: screenshot }, "zh"), screenshot);
  for (const message of [screenshot + " TARA_A100000038", "未知的指标说明"]) {
    assert.equal(warningMessage({ code, message }, "en"), message);
  }
  assert.equal(warningMessage({ code: "new_metric", message: screenshot }, "en"), screenshot);
});


test("all captured backend fixed Chinese warnings translate without mutating scientific diagnostics", () => {
  for (const warning of backendWarnings) {
    const english = warningMessage(warning, "en");
    assert.doesNotMatch(english, /[\u3400-\u9fff]/, warning.code + ": " + warning.message);
    assert.equal(warningMessage(warning, "zh"), warning.message);
    const detailed = { ...warning, message: warning.message + " TARA_A100000038; n=12" };
    assert.equal(warningMessage(detailed, "en"), detailed.message);
  }
});

test("both conditional paper denominator notes preserve their distinct scientific meanings", () => {
  const variants = backendWarnings.filter(warning => warning.code === "paper_denominator_difference");
  assert.equal(variants.length, 2);
  const current = variants.find(warning => warning.message.includes("保留功能不再二次归一化"))!;
  const author = variants.find(warning => warning.message.includes("当前榜单按作者脚本二次归一化"))!;
  assert.match(warningMessage(current, "en"), /retained functions are not renormalized again/);
  assert.match(warningMessage(author, "en"), /these percentages are not fractions of total diatom transcript signal/);
  for (const warning of variants) {
    assert.equal(warningMessage(warning, "zh"), warning.message);
    assert.equal(warningMessage({ ...warning, code: "unknown_scientific_note" }, "en"), warning.message);
  }
});
