"use client";

import { ArrowUpRight, BarChart3, Database, FileSearch, GitBranch } from "lucide-react";

import { useLanguage } from "@/components/language-provider";

type ProjectIntroProps = { variant: "auth" | "workspace" };

const resources = [
  {
    name: "Tara Oceans",
    href: "https://fondationtaraocean.org/expedition/tara-oceans/",
    description: "了解 Tara Oceans 航次与研究背景",
  },
  {
    name: "Ocean Gene Atlas",
    href: "https://oga.mio.osupytheas.fr/ocean-gene-atlas/",
    description: "在独立网站探索海洋基因分布",
  },
] as const;

export function ProjectIntro({ variant }: ProjectIntroProps) {
  const { t } = useLanguage();

  return (
    <section className={`project-intro project-intro-${variant}`} aria-labelledby={`project-intro-title-${variant}`}>
      <p className="project-intro-kicker">{t("认识 Tara Agent")}</p>
      <h2 id={`project-intro-title-${variant}`}>{t("用自然语言探索海洋科学数据")}</h2>
      <p className="project-intro-lead">
        {t("Tara Oceans 航次调查全球海洋浮游生物及其环境。Tara Agent 将已接入的样本、18S 群落和可用的基因功能数据连接到可追溯的分析流程。")}
      </p>

      <div className="project-intro-capabilities" aria-label={t("Tara Agent 能做什么")}>
        <div><FileSearch size={18} aria-hidden="true" /><span>{t("查找样本与生物类群")}</span></div>
        <div><BarChart3 size={18} aria-hidden="true" /><span>{t("分析丰度、多样性与环境关联")}</span></div>
        <div><Database size={18} aria-hidden="true" /><span>{t("探索可用的基因功能数据")}</span></div>
        <div><GitBranch size={18} aria-hidden="true" /><span>{t("查看图表、来源与分析链路")}</span></div>
      </div>

      <div className="project-intro-details">
        <div className="project-intro-guide">
          <h3>{t("如何开始")}</h3>
          <ol>
            <li>{variant === "auth"
              ? t("登录或以游客身份进入，选择一个示例问题。")
              : t("选择下方示例问题，或自己输入一句研究问题。")}</li>
            <li>{t("尽量说明类群、V4/V9、海区或环境变量等分析范围。")}</li>
            <li>{t("查看结果图表、数据说明与执行链路，再继续追问。")}</li>
          </ol>
        </div>

        <div className="project-intro-resources">
          <h3>{t("相关资源")}</h3>
          <div className="project-intro-links">
            {resources.map((resource) => (
              <a key={resource.name} href={resource.href} target="_blank" rel="noopener noreferrer">
                <span><strong>{resource.name}</strong><small>{t(resource.description)}</small></span>
                <ArrowUpRight size={17} aria-hidden="true" />
                <span className="sr-only">{t("（在新标签页打开）")}</span>
              </a>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}
