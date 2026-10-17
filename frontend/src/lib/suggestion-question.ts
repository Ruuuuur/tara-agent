import type { Language } from "./i18n";

type QuestionRule = [RegExp, (...values: string[]) => string];

const environmentLabels: Record<string, string> = {
  "温度": "temperature",
  "叶绿素 a": "chlorophyll a",
  "硝酸盐与亚硝酸盐": "nitrate plus nitrite",
  "磷酸盐": "phosphate",
  "硅酸盐": "silicate",
  "光合有效辐射": "photosynthetically active radiation",
  "绝对纬度": "absolute latitude",
  "混合层深度": "mixed-layer depth",
};

// 只翻译应用生成的完整问题模板；捕获的数据值、样本编号和科学口径保持原样。
const rules: QuestionRule[] = [
  [/^(.+?) 中收录了哪些 Tara 样本？$/, (region) => `Which Tara samples are available in ${region}?`],
  [/^有哪些 (.+?) 水层的样本可用于分析？$/, (depth) => `Which samples from the ${depth} layer are available for analysis?`],
  [/^筛选粒径范围为 (.+?) 的样本$/, (size) => `Find samples with a size fraction of ${size}.`],
  [/^列出数据中的极地样本$/, () => "List the polar samples in the dataset."],
  [/^列出数据中的非极地样本$/, () => "List the non-polar samples in the dataset."],
  [/^哪些样本的温度不低于 (.+?) 摄氏度？$/, (value) => `Which samples have a temperature of at least ${value} degrees Celsius?`],
  [/^哪些样本的温度不高于 (.+?) 摄氏度？$/, (value) => `Which samples have a temperature of at most ${value} degrees Celsius?`],
  [/^查找 (.+?) 中 (.+?) 水层的样本$/, (region, depth) => `Find samples from the ${depth} layer in ${region}.`],
  [/^查找 (.+?) 水层且粒径为 (.+?) 的样本$/, (depth, size) => `Find samples from the ${depth} layer with a size fraction of ${size}.`],
  [/^样本 (.+?) 是在哪里、什么环境下采集的？$/, (sample) => `Where was sample ${sample} collected, and what were its environmental conditions?`],
  [/^(V4|V9) 中有哪些属于 (.+?) 的 ASV，在哪些样本检出？$/, (marker, taxon) => `Which ${marker} ASVs belong to ${taxon}, and in which samples were they detected?`],
  [/^(V4|V9) 中 (.+?) 在各样本的相对丰度如何？$/, (marker, taxon) => `What is the relative abundance of ${taxon} across ${marker} samples?`],
  [/^(V4|V9) 中 (.+?) 的相对丰度与(温度|叶绿素 a|硝酸盐与亚硝酸盐|磷酸盐|硅酸盐|光合有效辐射|绝对纬度|混合层深度)是否相关？$/, (marker, taxon, variable) => `Is the relative abundance of ${taxon} in ${marker} samples associated with ${environmentLabels[variable]}?`],
  [/^(V4|V9) 的 Shannon 多样性在不同海区间有何差异？$/, (marker) => `How does ${marker} Shannon diversity differ among ocean regions?`],
  [/^比较不同海区的 (V4|V9) 观测 ASV 丰富度$/, (marker) => `Compare observed ${marker} ASV richness among ocean regions.`],
  [/^不同采样水层的 (V4|V9) Shannon 多样性如何？$/, (marker) => `How does ${marker} Shannon diversity vary among sampling depths?`],
  [/^按采样水层比较 (V4|V9) 的观测 ASV 丰富度$/, (marker) => `Compare observed ${marker} ASV richness by sampling depth.`],
  [/^不同粒径范围的 (V4|V9) Shannon 多样性有何差异？$/, (marker) => `How does ${marker} Shannon diversity differ among size fractions?`],
  [/^按粒径范围比较 (V4|V9) 的观测 ASV 丰富度$/, (marker) => `Compare observed ${marker} ASV richness by size fraction.`],
  [/^比较极地与非极地样本的 (V4|V9) Shannon 多样性$/, (marker) => `Compare ${marker} Shannon diversity between polar and non-polar samples.`],
  [/^极地与非极地样本的 (V4|V9) 观测 ASV 丰富度有何差异？$/, (marker) => `How does observed ${marker} ASV richness differ between polar and non-polar samples?`],
  [/^分别比较 V4 与 V9 群落的海区间 ASV 丰富度和 Shannon 多样性，两种标记的趋势是否一致？$/, () => "Compare ASV richness and Shannon diversity among ocean regions separately for V4 and V9 communities. Are the trends consistent between the two markers?"],
  [/^在全部已准备的 (MetaG|MetaT) 样本中，(.+?) 的哪些 Pfam 相对信号最高？列出前 100 项、各项贡献及样本覆盖率。$/, (assay, taxon) => `Across all prepared ${assay} samples, which Pfam families have the highest relative signals in ${taxon}? List the top 100, their contributions, and sample coverage.`],
  [/^(MetaG|MetaT) 样本 (.+?) 中，(.+?) 的哪些候选 Pfam 信号最高？列出前 10 项及相对份额。$/, (assay, sample, taxon) => `Which candidate Pfam signals are highest in ${taxon} in ${assay} sample ${sample}? List the top 10 and their relative shares.`],
  [/^选取一个有记录的 (MetaG|MetaT) (.+?) 样本，比较不加 E 条件与 min_iEvalue ≤ 1e-5 时的前 10 项 Pfam 排名和注释覆盖。$/, (assay, taxon) => `Select a recorded ${assay} ${taxon} sample and compare the top 10 Pfam rankings and annotation coverage without an E-value filter and with min_iEvalue ≤ 1e-5.`],
];

const followups = [
  ["请在全部符合条件的样本中按相对丰度降序排序，查看最高样本的海区、水层、粒径和环境信息，再列出该样本中占比最高的属。", "Rank all matching samples by relative abundance in descending order. Examine the ocean region, depth, size fraction, and environmental conditions of the highest-ranked sample, then list its most abundant genera."],
  ["按站点分别给出样本相对丰度均值和最大值的排名，保留各站点的有效样本数。", "Rank stations separately by the mean and maximum sample relative abundance, retaining the number of valid samples at each station."],
] as const;

export function translateSuggestionQuestion(question: string, language: Language): string {
  if (language === "zh") return question;
  for (const [source, target] of followups) {
    if (question.endsWith(source)) {
      const base = question.slice(0, -source.length);
      const translated = translateSuggestionQuestion(base, language);
      return translated === base ? question : `${translated} ${target}`;
    }
  }
  for (const [pattern, render] of rules) {
    const match = pattern.exec(question);
    if (match) return render(...match.slice(1));
  }
  return question;
}
