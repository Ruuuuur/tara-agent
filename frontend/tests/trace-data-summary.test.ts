import { strict as assert } from "node:assert";
import { test } from "node:test";
import { translateUi } from "../src/lib/i18n";
import { summarizeDataFilters } from "../src/lib/trace-data-summary";

test("trace summaries translate generated filter values, counts and long-list wrappers", () => {
  const filters = {query: {taxon: "Bacillariophyta", assay: "MetaT", sample_names: ["A", "B", "C"],
    sampling_keys: ["X", "Y", "Z"], polar: true, group_by: "ocean_region", limit: 20}};
  const saved = structuredClone(filters);
  const tags = summarizeDataFilters("function_profile", filters, "en");
  assert.ok(tags.some(tag => tag.value === "Diatoms" || tag.value === "diatoms"));
  assert.ok(tags.some(tag => tag.value === "A, B etc. (3 items)" && tag.detail === "A, B, C"));
  assert.ok(tags.some(tag => tag.value === "20 items"));
  for (const tag of tags) assert.doesNotMatch(tag.value, /[\u3400-\u9fff]/);
  assert.deepEqual(filters, saved);
  assert.ok(summarizeDataFilters("function_atlas", {sample_names: null}, "en").some(tag => tag.value === "All available samples"));
});

test("trace summaries retain original names and explicitly distinguish raw data from generated summaries", () => {
  const filters = {taxon: "原始分类名称", sample_name: "原始样本", environment_variable: "原始变量", group_by: "原始分组"};
  assert.deepEqual(summarizeDataFilters("function_profile", filters, "en").map(tag => tag.value),
    ["原始分类名称", "原始样本", "原始变量", "原始分组"]);
  assert.ok(summarizeDataFilters("function_atlas", {sample_names: null}).some(tag => tag.value === "全部可用样本"));
});

test("trace tool node names use a complete fixed template and retain identifiers", () => {
  const name = "function_atlas";
  assert.equal(translateUi("调用 MCP 工具 " + name, "en"), "Call MCP tool " + name);
  assert.equal(translateUi("调用 MCP 工具 " + name, "zh"), "调用 MCP 工具 " + name);
});
