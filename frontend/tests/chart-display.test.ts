import { strict as assert } from "node:assert";
import { test } from "node:test";
import { artifactTitle } from "../src/lib/artifact-presentation";
import { chartPresentation } from "../src/lib/chart-presentation";
import { translateLabel } from "../src/lib/i18n";
import { processPresentation } from "../src/lib/process-presentation";
import type { ChartSpec, AgentStep } from "../src/lib/types";
import axes from "./fixtures/chart-axes.json";

const screenshotTitle = "图2b/c与S6对照 · V4 · SRF · 20-180 μm · exp(Shannon)有效ASV数随纬度变化";
const expectedTitle = "V4 · SRF · 20-180 μm · exp(Shannon) effective ASV count vs latitude";

function chart(title: string): ChartSpec {
  return {
    kind: "scatter", title, x: [-60, 80], y: [2.5, 100],
    x_label: "纬度（°）", y_label: "exp(Shannon)有效ASV数",
    labels: ["TARA_A100000038", "原始分类注释"],
    series: [{ name: "MetaG", values: [0, null] }],
    artifact_key: "ordinations", result_role: "final",
  };
}

test("screenshot chart title and both actual Plotly axis fields are localized", () => {
  const original = chart(screenshotTitle);
  const displayed = chartPresentation(original, "en");
  assert.equal(displayed.title, expectedTitle);
  assert.equal(displayed.x_label, "Latitude (°)");
  assert.equal(displayed.y_label, "exp(Shannon) effective ASV count");
  assert.equal(translateLabel(artifactTitle(screenshotTitle), "en"), expectedTitle);
  assert.strictEqual(chartPresentation(original, "zh"), original);
  assert.equal(original.title, screenshotTitle);
  for (const key of ["x", "y", "labels", "series"] as const) assert.strictEqual(displayed[key], original[key]);
  assert.equal(displayed.artifact_key, original.artifact_key);
  assert.equal(displayed.result_role, original.result_role);
  assert.equal(chartPresentation(displayed, "en").title, expectedTitle);
});

test("screenshot fixed process description uses a complete English sentence", () => {
  const step: AgentStep = { stage: "answer", title: "组织可追踪答案", detail: "根据工具结果生成回答、警告、来源和图表数据。" };
  const shown = processPresentation(step);
  assert.equal(translateLabel(shown.title, "en"), "Summarize analysis results");
  assert.equal(translateLabel(shown.detail, "en"), "Generate the answer, warnings, sources and chart data from tool results.");
  assert.equal(translateLabel(shown.detail, "zh"), step.detail);
  assert.equal(step.title, "组织可追踪答案");
});

// 包含核心和条件开放工具的全部动态图标题形状，并保留不同标记、单位和统计参数。
const titles = [
  screenshotTitle,
  "步骤 2 · 图2b/c与S6对照 · V9 · DCM · 180-2000 μm · 群落相对丰度随纬度变化",
  "图2a/S6对照 · V4 · 20-180 μm表层群落相对丰度",
  "图3a对照 · V9 · 群落丰度和Shannon与环境Spearman关联",
  "图3a对照 · exp_shannon · 环境PLS（42组）",
  "图3b对照 · V4 · 四粒径NMDS（Stress1=0.1234）",
  "图9a对照 · 当前数据 · Top 100 功能相对转录贡献",
  "图9a对照 · 作者参考重算 · Top 100 功能相对转录贡献",
  "图9b对照 · 当前数据 · Top 100 功能粒径分配",
  "图9c对照 · 当前数据 · Top 100 功能海区分配",
  "图10b对照 · 当前数据 · DUF285 环境PLS相关圆（31组）",
  "图10e对照 · 当前数据 · LHC亚家族 环境PLS相关圆（246组）",
  "图10e对照 · 作者参考重算 · LHC亚家族 环境PLS相关圆（12组）",
  "temperature与PF00069 MetaG信号",
  "PF00069 采样编码对应的相对功能信号",
  "temperature 与相对丰度",
  "本次返回站点的相对丰度均值",
  "本次返回站点的相对丰度最大值",
];
test("screenshot LHC target is translated inside the PLS template without changing chart data", () => {
  const original = chart("图10e对照 · 当前数据 · LHC亚家族 环境PLS相关圆（246组）");
  const shown = chartPresentation(original, "en");
  assert.equal(shown.title, "Current data · LHC subfamilies environmental PLS correlation circle (246 groups)");
  assert.equal(translateLabel("LHC亚家族", "en"), "LHC subfamilies");
  assert.strictEqual(shown.x, original.x);
  assert.strictEqual(shown.y, original.y);
  assert.strictEqual(shown.labels, original.labels);
  assert.strictEqual(shown.series, original.series);
  assert.strictEqual(chartPresentation(original, "zh"), original);
});
for (const title of titles) {
  test(`complete dynamic chart display: ${title}`, () => {
    const displayed = chartPresentation(chart(title), "en");
    assert.doesNotMatch(displayed.title, /[\u3400-\u9fff]/);
    assert.ok(displayed.title.length > 0);
    assert.equal(chartPresentation(chart(title), "zh").title, title);
    for (const token of title.match(/(?:V[49]|PF\d+|DUF285|Stress1=[\d.]+|20-180|180-2000|100|42|31)/g) ?? []) {
      assert.ok(displayed.title.includes(token), token);
    }
  });
}
for (const axis of [...axes, "样本相对丰度均值", "样本相对丰度最大值", "群落相对丰度", "exp(Shannon)有效ASV数"]) {
  test(`complete axis label: ${axis}`, () => {
    const displayed = chartPresentation({ ...chart("Title"), x_label: axis, y_label: axis }, "en");
    assert.doesNotMatch(displayed.x_label, /[\u3400-\u9fff]/);
    assert.equal(displayed.x_label, displayed.y_label);
    assert.equal(translateLabel(axis, "zh"), axis);
    assert.ok(displayed.x_label.length > 0);
  });
}
for (const tool of ["function_study", "compare_function_signals", "function_environment", "community_analysis", "function_atlas", "function_profile", "find_function_samples", "retrieve_gene_sequences", "taxon_abundance", "diversity_analysis", "environment_association", "find_samples", "get_sample_info", "find_taxa"]) {
  test(`process display preserves tool identifiers: ${tool}`, () => {
    const shown = processPresentation({ stage: "execute", title: "执行科学分析", detail: `已通过 MCP 调用白名单工具 ${tool}。` });
    const text = translateLabel(shown.detail, "en");
    assert.doesNotMatch(text, /[\u3400-\u9fff]/);
    assert.ok(text.includes(tool));
  });
}

test("map hover template translates labels without altering sample IDs or values", () => {
  const original: ChartSpec = { ...chart("样本分布"), kind: "sample_map", labels: [
    "TARA_001 SRF；相对丰度=0.0025；exp(Shannon)=12.3", "TARA_A100000038", "原始分类注释",
  ] };
  const shown = chartPresentation(original, "en");
  assert.equal(shown.labels[0], "TARA_001 SRF; relative abundance=0.0025; exp(Shannon)=12.3");
  assert.deepEqual(shown.labels.slice(1), original.labels.slice(1));
  assert.equal(original.labels[0], "TARA_001 SRF；相对丰度=0.0025；exp(Shannon)=12.3");
  assert.strictEqual(shown.x, original.x);
  assert.strictEqual(chartPresentation(original, "zh"), original);
});
