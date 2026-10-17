import { strict as assert } from "node:assert";
import { test } from "node:test";
import { translateSuggestionQuestion } from "../src/lib/suggestion-question";

const examples = [
  ["查找 DCM 水层且粒径为 20-180 的样本", "Find samples from the DCM layer with a size fraction of 20-180."],
  ["样本 TARA_A100000038 是在哪里、什么环境下采集的？", "Where was sample TARA_A100000038 collected, and what were its environmental conditions?"],
  ["V9 中 Opisthokonta 在各样本的相对丰度如何？", "What is the relative abundance of Opisthokonta across V9 samples?"],
  ["分别比较 V4 与 V9 群落的海区间 ASV 丰富度和 Shannon 多样性，两种标记的趋势是否一致？", "Compare ASV richness and Shannon diversity among ocean regions separately for V4 and V9 communities. Are the trends consistent between the two markers?"],
  ["North Atlantic Ocean 中收录了哪些 Tara 样本？", "Which Tara samples are available in North Atlantic Ocean?"],
  ["有哪些 SRF 水层的样本可用于分析？", "Which samples from the SRF layer are available for analysis?"],
  ["筛选粒径范围为 0.8-5 的样本", "Find samples with a size fraction of 0.8-5."],
  ["列出数据中的极地样本", "List the polar samples in the dataset."],
  ["列出数据中的非极地样本", "List the non-polar samples in the dataset."],
  ["哪些样本的温度不低于 -1.5 摄氏度？", "Which samples have a temperature of at least -1.5 degrees Celsius?"],
  ["哪些样本的温度不高于 20 摄氏度？", "Which samples have a temperature of at most 20 degrees Celsius?"],
  ["查找 South Pacific Ocean 中 DCM 水层的样本", "Find samples from the DCM layer in South Pacific Ocean."],
  ["V4 中有哪些属于 Bacillariophyta 的 ASV，在哪些样本检出？", "Which V4 ASVs belong to Bacillariophyta, and in which samples were they detected?"],
];

for (const [source, expected] of examples) {
  test(`suggestion preserves scope in English and Chinese: ${source}`, () => {
    assert.equal(translateSuggestionQuestion(source, "en"), expected);
    assert.equal(translateSuggestionQuestion(source, "zh"), source);
  });
}

for (const marker of ["V4", "V9"]) {
  for (const source of [
    `${marker} 的 Shannon 多样性在不同海区间有何差异？`,
    `比较不同海区的 ${marker} 观测 ASV 丰富度`,
    `不同采样水层的 ${marker} Shannon 多样性如何？`,
    `按采样水层比较 ${marker} 的观测 ASV 丰富度`,
    `不同粒径范围的 ${marker} Shannon 多样性有何差异？`,
    `按粒径范围比较 ${marker} 的观测 ASV 丰富度`,
    `比较极地与非极地样本的 ${marker} Shannon 多样性`,
    `极地与非极地样本的 ${marker} 观测 ASV 丰富度有何差异？`,
  ]) {
    test(`diversity suggestion retains marker and metric: ${source}`, () => {
      const translated = translateSuggestionQuestion(source, "en");
      assert.doesNotMatch(translated, /\p{Script=Han}/u);
      assert.ok(translated.includes(marker));
      assert.ok(translated.includes(source.includes("Shannon") ? "Shannon" : "observed"));
    });
  }
}

test("environment terms preserve combined nitrate and nitrite rather than changing the variable", () => {
  const terms: Record<string, string> = {
    "温度": "temperature", "叶绿素 a": "chlorophyll a", "硝酸盐与亚硝酸盐": "nitrate plus nitrite",
    "磷酸盐": "phosphate", "硅酸盐": "silicate", "光合有效辐射": "photosynthetically active radiation",
    "绝对纬度": "absolute latitude", "混合层深度": "mixed-layer depth",
  };
  for (const [source, expected] of Object.entries(terms)) {
    assert.equal(translateSuggestionQuestion(`V9 中 Bacillariophyta 的相对丰度与${source}是否相关？`, "en"),
      `Is the relative abundance of Bacillariophyta in V9 samples associated with ${expected}?`);
  }
});

test("multistep questions retain full-range ordering and distinct station statistics", () => {
  const base = "V4 中 Bacillariophyta 在各样本的相对丰度如何？";
  const context = base + "请在全部符合条件的样本中按相对丰度降序排序，查看最高样本的海区、水层、粒径和环境信息，再列出该样本中占比最高的属。";
  const station = base + "按站点分别给出样本相对丰度均值和最大值的排名，保留各站点的有效样本数。";
  assert.match(translateSuggestionQuestion(context, "en"), /all matching samples.*descending.*most abundant genera/);
  assert.match(translateSuggestionQuestion(station, "en"), /mean and maximum.*number of valid samples/);
  assert.doesNotMatch(translateSuggestionQuestion(context, "en"), /\p{Script=Han}/u);
});

test("functional questions retain assays, identifiers, thresholds and ranking sizes", () => {
  for (const assay of ["MetaG", "MetaT"]) {
    const questions = [
      `在全部已准备的 ${assay} 样本中，Bacillariophyta 的哪些 Pfam 相对信号最高？列出前 100 项、各项贡献及样本覆盖率。`,
      `${assay} 样本 80DCM1GGMM14 中，Bacillariophyta 的哪些候选 Pfam 信号最高？列出前 10 项及相对份额。`,
      `选取一个有记录的 ${assay} Bacillariophyta 样本，比较不加 E 条件与 min_iEvalue ≤ 1e-5 时的前 10 项 Pfam 排名和注释覆盖。`,
    ];
    for (const source of questions) {
      const translated = translateSuggestionQuestion(source, "en");
      assert.doesNotMatch(translated, /\p{Script=Han}/u);
      for (const value of [assay, "Bacillariophyta", "Pfam", ...(source.match(/80DCM1GGMM14|100|10|min_iEvalue ≤ 1e-5/g) ?? [])]) {
        assert.ok(translated.includes(value));
      }
    }
  }
});

test("unknown prose and scientific diagnostics remain unchanged", () => {
  const source = "未收录的问题：PF00001 温度 0.02，样本 TARA_A100000038";
  assert.equal(translateSuggestionQuestion(source, "en"), source);
});
