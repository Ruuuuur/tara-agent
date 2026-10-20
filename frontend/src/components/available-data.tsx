"use client";

import { Database } from "lucide-react";
import { useEffect, useState } from "react";

import { useLanguage } from "@/components/language-provider";
import { getHealth } from "@/lib/api";
import type { HealthResponse } from "@/lib/types";

const coreNames: Record<string, string> = {
  context_general: "样本与站位信息",
  context_stat: "环境数据",
  "18s_v4": "18S V4 ASV 群落",
  "18s_v9": "18S V9 ASV 群落",
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
        {core.map((dataset) => (
          <div className="available-data-item" key={dataset.key}>
            <span>{t(coreNames[dataset.key] ?? dataset.key)}</span>
            <small>{dataset.filename}</small>
          </div>
        ))}
        {matou ? (
          <>
            <p>{matou.dataset_version} · {matou.taxon}</p>
            <div className="available-data-item"><span>{t("分类注释")}</span><small>{matou.dataset_version}</small></div>
            <div className="available-data-item"><span>{t("Pfam 功能注释")}</span><small>{matou.dataset_version}</small></div>
            <div className="available-data-item"><span>MetaG · DNA</span><small>{t("{0} 个样本", [matou.sample_counts.MetaG ?? 0])}</small></div>
            <div className="available-data-item"><span>MetaT · RNA</span><small>{t("{0} 个样本", [matou.sample_counts.MetaT ?? 0])}</small></div>
            {matou.paper_reference_ready ? <p>{t("论文功能参考资料已准备")}</p> : null}
          </>
        ) : health ? <p>{t("当前服务未启用 MATOU 功能数据")}</p> : null}
        {failed ? <p>{t("暂时无法读取数据目录，请稍后刷新。")}</p> : null}
      </div>
    </details>
  );
}
