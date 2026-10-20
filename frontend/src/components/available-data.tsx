"use client";

import { Database } from "lucide-react";
import { useEffect, useState } from "react";

import { useLanguage } from "@/components/language-provider";
import { getHealth } from "@/lib/api";
import type { HealthResponse } from "@/lib/types";

const coreDescriptions: Record<string, { name: string; description: string }> = {
  context_general: {
    name: "样本与站位信息",
    description: "记录采样位置、海区、水层和粒径等背景，用于筛选和连接样本。",
  },
  context_stat: {
    name: "环境数据",
    description: "记录温度、盐度、营养盐等环境变量，用于探索环境关联。",
  },
  "18s_v4": {
    name: "18S V4 ASV 群落",
    description: "用 18S 的 V4 区域识别真核生物群落，读数可用于相对丰度和多样性分析。",
  },
  "18s_v9": {
    name: "18S V9 ASV 群落",
    description: "用 18S 的 V9 区域独立观察真核生物群落；与 V4 的结果需要分别核对。",
  },
};

export function AvailableData() {
  const { t } = useLanguage();
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    const controller = new AbortController();
    getHealth(controller.signal)
      .then(setHealth)
      .catch(() => { if (!controller.signal.aborted) setFailed(true); });
    return () => controller.abort();
  }, []);

  const core = health?.datasets.filter((dataset) => dataset.ready) ?? [];
  const matou = health?.matou;
  const count = core.length + (matou ? 4 : 0);

  return (
    <details className="available-data">
      <summary><Database size={15} aria-hidden="true" />{t("当前数据集")}{health ? ` (${count})` : ""}</summary>
      <div className="available-data-panel">
        <strong>{t("当前服务可用的数据")}</strong>
        {core.map((dataset) => {
          const item = coreDescriptions[dataset.key];
          return (
            <div className="available-data-item" key={dataset.key}>
              <span>{t(item?.name ?? dataset.key)}</span>
              {item ? <p>{t(item.description)}</p> : null}
              <small>{dataset.filename}</small>
            </div>
          );
        })}
        {matou ? (
          <>
            <p className="available-data-group">{matou.dataset_version} · {matou.taxon}</p>
            <div className="available-data-item"><span>{t("分类注释")}</span><p>{t("把基因关联到硅藻等生物类群，用于确定分析对象。")}</p></div>
            <div className="available-data-item"><span>{t("Pfam 功能注释")}</span><p>{t("把基因关联到蛋白结构域，作为功能分析的候选注释。")}</p></div>
            <div className="available-data-item"><span>MetaG · DNA</span><p>{t("基因在样本中的相对 DNA 信号，反映被测到的功能潜力。")}</p><small>{t("{0} 个样本", [matou.sample_counts.MetaG ?? 0])}</small></div>
            <div className="available-data-item"><span>MetaT · RNA</span><p>{t("转录本在样本中的相对 RNA 信号，反映被测到的转录活动。")}</p><small>{t("{0} 个样本", [matou.sample_counts.MetaT ?? 0])}</small></div>
            <p className="available-data-note">{t("MetaG/MetaT 是相对信号，不等于绝对基因拷贝数或表达量。")}</p>
            {matou.paper_reference_ready ? <p>{t("论文功能参考资料已准备")}</p> : null}
          </>
        ) : health ? <p>{t("当前服务未启用 MATOU 功能数据")}</p> : null}
        {failed ? <p>{t("暂时无法读取数据目录，请稍后刷新。")}</p> : null}
      </div>
    </details>
  );
}
