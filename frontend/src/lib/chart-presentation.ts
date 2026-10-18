import { artifactTitle } from "./artifact-presentation";
import { translateLabel, type Language } from "./i18n";
import type { ChartSpec } from "./types";

// 只生成图表的显示标签，原始坐标、样本标识、系列和工具结果均保持原样。
export function chartPresentation(chart: ChartSpec, language: Language): ChartSpec {
  if (language === "zh") return chart;
  return {
    ...chart,
    title: translateLabel(artifactTitle(chart.title), language),
    x_label: translateLabel(chart.x_label, language),
    y_label: translateLabel(chart.y_label, language),
    labels: chart.kind === "sample_map" ? chart.labels.map((label) => {
      // 后端生成的地图提示使用完整模板；保留站点、数值和未知原始标签。
      const sample = /^(.+ SRF)；相对丰度=([^；]+)；exp\(Shannon\)=(.+)$/.exec(label);
      return sample ? `${sample[1]}; relative abundance=${sample[2]}; exp(Shannon)=${sample[3]}` : label;
    }) : chart.labels,
  };
}
