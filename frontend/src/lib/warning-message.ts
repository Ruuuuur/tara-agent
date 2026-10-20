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

// 同一提示代码在不同分析服务中保留过不同完整表述；按原句匹配，未知附加诊断仍原样显示。
const messageVariants: Array<[string, string, string]> = [
  ["candidate_annotation", "Pfam 是候选结构域关联，不证明生物学功能；统一 E 条件不替代家族 gathering 阈值。", "Pfam indicates candidate domain associations, not established biological function. A uniform E-value criterion does not replace family-specific gathering thresholds."],
  ["candidate_annotation", "结果描述候选 Pfam 关联，不证明生物学功能或解决翻译框冲突。", "Results describe candidate Pfam associations; they do not establish biological function or resolve reading-frame conflicts."],
  ["candidate_evalue_condition", "统一 i-Evalue 条件不是 Pfam 家族的官方 gathering 阈值。", "The uniform i-Evalue criterion is not the official family-specific Pfam gathering threshold."],
  ["candidate_relative_signal", "候选Pfam信号不等于蛋白活性；相对信号不等于绝对表达。缺失不补零。", "Candidate Pfam signals do not measure protein activity, and relative signals do not measure absolute expression. Missing values are not replaced with zero."],
  ["complete_case_description", "相关仅使用两侧都有观测且分母为正的记录；缺失不补零，rho 不作为显著性、因果或差异表达检验。", "Correlations use only records observed on both sides with positive denominators. Missing values are not replaced with zero; rho is not a test of significance, causality, or differential expression."],
  ["method_scope", "V4/V9独立计算；测序信号不等于细胞数；Shannon未稀释。零目标库多样性未定义。", "V4 and V9 are calculated independently. Sequencing signals are not cell counts. Shannon diversity is not rarefied. Diversity is undefined for libraries with zero target reads."],
  ["missing_filter_values_excluded", "应用其他样本筛选条件后，温度值缺失的样本未参与温度筛选。", "After other sample filters were applied, samples with missing temperature values were excluded from temperature filtering."],
  ["nonexclusive_domains", "功能合并沿用作者对Pfam信号求和的规则；共享基因与多结构域不分摊，不能解释为互斥基因组成、蛋白活性或RNA/DNA活性。", "Function aggregation follows the authors' rule of summing Pfam signals. Shared genes and multiple domains are not apportioned; these values cannot be interpreted as mutually exclusive gene composition, protein activity, or RNA/DNA activity."],
  ["observed_records_only", "仅汇总输入中实际提供的类群基因记录；未出现记录不补零。", "Only taxon-gene records actually supplied in the input are aggregated. Absent records are not replaced with zero."],
  ["ordination_method", "NMDS采用固定种子单调SMACOF、Bray–Curtis和Stress1；不声称与vegan metaMDS的随机坐标、自动转换或论文stress完全一致。", "NMDS uses fixed-seed monotonic SMACOF, Bray-Curtis distances, and Stress1. Its random coordinates, transformations, and stress are not claimed to match vegan metaMDS or the paper exactly."],
  ["ranking_scope", "总体排名按有正分母的原始样本等权计算已观测贡献，未出现记录不补为生物学零；观测覆盖同时报告。未合并重复采样或近似粒径，不是论文图9的精确复现。", "Overall rankings use equal weights across original samples with positive denominators to summarize observed contributions. Absent records are not treated as biological zeros, and observed coverage is reported. Replicate samples and approximate size fractions are not merged; this is not an exact reproduction of Figure 9."],
  ["reference_scope", "paper_reference使用作者公开汇总表；current_data使用当前唯一gene–Pfam候选映射，仅保留DNA11/cDNA14。两者的结构域计数、样本范围和分母不同，不能声称精确复现。", "paper_reference uses the authors' public summary tables; current_data uses the current unique gene-Pfam candidate mapping and retains only DNA11/cDNA14. Domain counts, sample coverage, and denominators differ, so exact reproduction cannot be claimed."],
  ["relative_observed_signal", "仅比较样本内已提供数值的相对贡献，不解释为绝对表达、RNA/DNA 活性或蛋白活性。", "Only the relative contributions of supplied values within each sample are compared; they do not measure absolute expression, RNA/DNA activity, or protein activity."],
  ["sample_mapping_unconfirmed", "样本名来自定量文件；名称筛选不解释采样条件，不证明 DNA/RNA 配对或 context 关联。", "Sample names come from quantification files. Filtering by name does not establish sampling conditions, DNA/RNA pairing, or links to context data."],
  ["sampling_code_correspondence", "按版本化作者编码规则精确匹配站位、水层、批次与原始过滤组，仅比较 DNA11 与 cDNA14。编码对应不证明同一提取物；不合并 WGA、重复或近似过滤组，不计算 RNA/DNA 活性。", "Station, depth, batch, and original filtration groups are matched exactly using versioned author coding rules; only DNA11 and cDNA14 are compared. Matching codes do not prove a shared extract. WGA, replicates, and approximate filtration groups are not merged, and RNA/DNA activity is not calculated."],
  ["shared_genes", "每个 gene–Pfam 对仅计一次；不同家族可共享基因，份额不可相加为 100%。", "Each gene-Pfam pair is counted once. Different families can share genes, so their fractions cannot be summed to 100%."],
  ["shared_genes_between_families", "不同 Pfam 共享基因，各功能份额相加可能超过 100%。", "Different Pfam families can share genes, so the sum of function fractions may exceed 100%."],
  ["statistical_scope", "双侧Spearman置换检验；一个PANGAEA样本一行。相关仅作探索，不证明因果；未校正建库方法、航次、站位重复及其他环境混杂，须按已核实方法分层核验。", "Two-sided Spearman permutation tests use one row per PANGAEA sample. Correlations are exploratory and do not establish causality. Library preparation methods, cruises, repeated stations, and other environmental confounders were not adjusted for; stratified verification using confirmed methods is required."],
  ["statistical_scope", "相关采用双侧置换检验和BH校正；PLS仅描述。站位/水层/粒径观测并非必然独立，未经设计验证不能推断因果。", "Correlations use two-sided permutation tests and BH correction; PLS is descriptive only. Observations across stations, depths, and size fractions are not necessarily independent, and causality cannot be inferred without a validated study design."],
  ["supplemental_environment_context", "部分环境值来自按确切样本ID核验的补充资料；测量方法、统计口径和时空间隔见逐点证据，不等同于同步水样实测。", "Some environmental values come from supplementary sources verified by exact sample ID. See the per-point evidence for measurement methods, statistical definitions, and spatial and temporal separation; these are not equivalent to simultaneous water-sample measurements."],
  ["unconfirmed_export_unit", "份额仅针对提供的数值；不称为原始 RPKM、绝对表达量或 RNA/DNA 活性。", "Fractions apply only to the supplied values; they are not described as raw RPKM, absolute expression, or RNA/DNA activity."],
  ["zero_observed_denominator", "没有正的输入总信号，份额未定义；不据此认定样本中生物学功能缺失。", "There is no positive total input signal, so fractions are undefined. This does not establish the absence of a biological function in the sample."],
  [
    "read_count_is_not_cell_abundance",
    "测序读数是测序观测信号，不能直接解释为细胞丰度。",
    "Sequencing read counts are sequencing observations and cannot be interpreted directly as cell abundance.",
  ],
];

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
  "模型服务暂时不可用，请稍后重试。": "The model service is temporarily unavailable. Please try again later.",
  "模型返回了无效的分析决定": "The model returned an invalid analysis decision.",
  "模型未返回有效的分析工具，请重新提问。": "The model did not return a valid analysis tool. Please rephrase your question.",
};

export function warningMessage(warning: Pick<ResultWarning, "code" | "message">, language: Language): string {
  if (language === "zh") return warning.message;
  const known = messages[warning.code];
  if (known?.[0] === warning.message) return known[1];
  const variant = messageVariants.find(([code, message]) => code === warning.code && message === warning.message);
  if (variant) return variant[2];
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
