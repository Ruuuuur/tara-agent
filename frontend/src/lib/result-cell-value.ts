import type { Language } from "./i18n";
import { taxonomyCellValue } from "./taxonomy-label";

// 仅按列和完整原句匹配程序说明；未知诊断、科学名称和原始导出值保持原样。
const functionStudyLabels: Record<string, Record<string, string>> = {
  "target": {
    "LHC亚家族": "LHC subfamilies"
  },
  "output": {
    "功能排名与相对转录贡献": "Function ranking and relative transcript contribution",
    "粒径分配": "Size-fraction allocation",
    "海区分配": "Ocean-region allocation",
    "DUF285环境关联": "DUF285 environmental associations",
    "LHC亚家族环境关联": "LHC subfamily environmental associations"
  },
  "reason": {
    "没有可用结果": "No results are available.",
    "水层或实验协议不在当前方法范围": "The depth layer or experimental protocol is outside the scope of the current method.",
    "完整观测不足4组，无法稳定提取两个成分": "Fewer than four complete groups are available; two components cannot be extracted reliably.",
    "存在常量变量，标准化未定义": "Constant variables are present, so standardization is undefined.",
    "环境矩阵秩不足2": "The environmental matrix has rank below two.",
    "响应残差信号不足，成分未定义": "The residual response signal is insufficient; the component is undefined.",
    "环境与响应无可提取协变信号": "No extractable covariance remains between the environment and response.",
    "成分方差未定义": "The component variance is undefined.",
    "响应载荷未定义": "The response loading is undefined.",
    "PLS迭代100次未收敛": "PLS did not converge within 100 iterations.",
    "相关坐标存在未定义值": "The correlation coordinates contain undefined values.",
    "需要以作者逐geneID亚家族注释与当前MetaG/MetaT基因信号预计算的lhc_profiles；PF00504总量不能代替LHCf/LHCq/LHCr/LHCx/LHCz。作者公开Pfam汇总表不能还原亚家族。": "lhc_profiles must be precomputed from the authors' gene-level subfamily annotations and the current MetaG/MetaT gene signals. Total PF00504 signal cannot substitute for LHCf/LHCq/LHCr/LHCx/LHCz. The authors' public Pfam summary tables cannot reconstruct subfamilies."
  }
};

export function resultCellValue(column: string, row: Record<string, unknown>, language: Language): unknown {
  const value = taxonomyCellValue(column, row, language);
  const labels = functionStudyLabels[column];
  return language === "en" && typeof value === "string"
    && Object.hasOwn(functionStudyLabels, column) && Object.hasOwn(labels, value)
    ? labels[value]
    : value;
}
