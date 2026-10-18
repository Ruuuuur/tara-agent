import type { Language } from "./i18n";
import type { ResultWarning } from "./types";

// 只翻译已知代码对应的完整应用提示，避免改写科学数据和未知诊断。
const messages: Record<string, [string, string]> = {
  unrarefied_diversity: [
    "观测丰富度和 Shannon 指数基于未经稀释抽样的测序读数计算，测序量差异可能影响样本间比较。",
    "Observed richness and the Shannon index are calculated from unrarefied sequencing read counts. Differences in sequencing depth may affect comparisons between samples.",
  ],
  read_count_is_not_cell_abundance: [
    "原始测序读数及据此计算的相对丰度属于测序信号，不是对细胞丰度的直接测量。",
    "Raw read counts and the relative abundances calculated from them represent sequencing signals, not direct measurements of cell abundance.",
  ],
  samples_missing_marker_excluded: [
    "不含所请求标记数据的背景样本未参与本次分析。",
    "Background samples without data for the requested marker were excluded from this analysis.",
  ],
  missing_environment_values_excluded: [
    "环境变量缺失的样本未参与成对相关性计算。",
    "Samples with missing environmental values were excluded from pairwise correlation calculations.",
  ],
  missing_group_values_excluded: [
    "分组变量缺失的样本未纳入分组汇总。",
    "Samples with missing grouping values were excluded from group summaries.",
  ],
  taxon_not_found: ["没有 ASV 匹配请求的分类单元。", "No ASVs match the requested taxon."],
  zero_reads_in_analysis_set: [
    "所选 ASV 集合的测序读数为零时，Shannon 指数没有定义。",
    "The Shannon index is undefined when the selected ASVs have zero sequencing reads.",
  ],
  zero_read_library: [
    "样本总测序读数为零时，相对丰度没有定义。",
    "Relative abundance is undefined when a sample has zero total sequencing reads.",
  ],
  asymptotic_p_value_caution: [
    "SciPy 文档说明，Spearman 渐近 p 值在样本量大于 500 时最准确；当前探索性 p 值需要谨慎解释。",
    "According to the SciPy documentation, asymptotic Spearman p-values are most accurate for sample sizes greater than 500. Interpret these exploratory p-values with caution.",
  ],
  insufficient_samples: [
    "Spearman 相关性计算至少需要三个数据完整的样本。",
    "Spearman correlation requires at least three samples with complete data.",
  ],
  constant_input: [
    "输入值全部相同时，Spearman 相关系数没有定义。",
    "Spearman correlation is undefined when all input values are identical.",
  ],
  undefined_correlation: [
    "Spearman 相关性计算未得到有限数值结果。",
    "The Spearman correlation calculation did not produce a finite result.",
  ],
  station_descriptive_aggregation: [
    "站点均值为有效样本相对丰度的等权平均，最大值为最高样本值；不同水层和粒径合并仅作描述，不是独立重复或站点绝对丰度。",
    "Station means are equally weighted means of valid sample relative abundances, and maxima are the highest sample values. Combining depths and size fractions is descriptive only; these are not independent replicates or absolute station abundances.",
  ],
  taxonomy_assignment_limit: [
    "属/种名称来自原始分类注释；截短、占位或不支持的层级保留为未鉴定。未按置信度剔除；测序信号不证明种鉴定或细胞丰度。组成分别给出全样本占比和所选类群内部占比。",
    "Genus and species names come from the original taxonomic annotations. Truncated, placeholder or unsupported ranks remain unidentified. No confidence-based filtering was applied; sequencing signals do not establish species identification or cell abundance. Composition is reported both as a fraction of the whole sample and within the selected taxon.",
  ],
  missing_station_excluded: [
    "缺少站点标识的样本未参与站点汇总。",
    "Samples without station identifiers were excluded from station summaries.",
  ],
};

const stopReasons: Record<string, string> = {
  "契约纠正次数已用尽；保留已完成结果。": "The input correction limit was reached. Completed results have been retained.",
  "分析时间或规划轮数预算已用尽；保留已完成结果。": "The analysis time or planning round limit was reached. Completed results have been retained.",
  "工具调用预算已用尽；保留已完成结果。": "The tool call limit was reached. Completed results have been retained.",
  "计划请求了当前不可用的工具，已停止。": "The plan requested an unavailable tool, so analysis stopped.",
  "检测到重复工具调用，没有新的分析进展，已停止。": "A repeated tool call made no new progress, so analysis stopped.",
  "重复提交已拒绝的参数，没有纠正进展，已停止。": "Rejected arguments were submitted again without correction, so analysis stopped.",
  "尚无工具证据，不能声称分析完成。": "There is no tool evidence yet, so the analysis cannot be reported as complete.",
  "分析时间预算已用尽；保留已完成结果。": "The analysis time limit was reached. Completed results have been retained.",
  "部分科学结果尚未完成，请查看对应项目状态和原因。": "Some scientific results are incomplete. Check the status and reason for each item.",
  "分析时间预算已用尽；已完成的工具结果保留在下方。": "The analysis time limit was reached. Completed tool results are retained below.",
};
const failurePrefixes: Array<[string, string]> = [
  ["下一步规划未完成，已停止并保留已完成结果：", "Planning the next step did not complete. Analysis stopped and completed results were retained: "],
  ["步骤未完成，已停止且不自动重试：", "The step did not complete. Analysis stopped without an automatic retry: "],
  ["工具输入契约不可用，已停止：", "The tool input contract is unavailable, so analysis stopped: "],
];
const failureReasons: Record<string, string> = {
  "模型返回了无效的分析决定": "The model returned an invalid analysis decision.",
  "模型未返回有效的分析工具，请重新提问。": "The model did not return a valid analysis tool. Please rephrase your question.",
};

export function warningMessage(warning: Pick<ResultWarning, "code" | "message">, language: Language): string {
  if (language === "zh") return warning.message;
  const known = messages[warning.code];
  if (known?.[0] === warning.message) return known[1];
  if (warning.code === "analysis_incomplete") {
    if (Object.hasOwn(stopReasons, warning.message)) return stopReasons[warning.message];
    for (const [source, target] of failurePrefixes) {
      if (warning.message.startsWith(source)) {
        const detail = warning.message.slice(source.length);
        return target + (Object.hasOwn(failureReasons, detail) ? failureReasons[detail] : detail);
      }
    }
  }
  return warning.message;
}
