"use client";

import { ArrowUpRight, BarChart3, Check, Copy, Database, FileSearch, GitBranch } from "lucide-react";
import { useState } from "react";

import { useLanguage } from "@/components/language-provider";

type ProjectIntroProps = { variant: "auth" | "workspace" };

const resources = [
  {
    name: "Tara Oceans",
    href: "https://www.tara-oceans-science.org/tara-oceans-expedition/",
    description: "了解 Tara Oceans 航次与研究背景",
  },
  {
    name: "Ocean Gene Atlas",
    href: "https://oga.mio.osupytheas.fr/ocean-gene-atlas/",
    description: "在独立网站探索海洋基因分布",
  },
  {
    name: "硅藻全球分布论文",
    href: "https://www.nature.com/articles/s41467-025-58027-7",
    description: "阅读 Nature Communications 的硅藻研究",
  },
] as const;

const beginnerPrompts = [
  {
    label: "示例 A：查询样本信息",
    description: "先了解样本在哪里采集、有哪些环境记录。",
    prompt: "Where was sample TARA_A100000032 collected, and what were its environmental conditions?",
  },
  {
    label: "示例 B：比较不同海区的多样性",
    description: "分别查看 V4、V9 的多样性趋势。",
    prompt: "Compare ASV richness and Shannon diversity among ocean regions separately for V4 and V9 communities. Are the trends consistent between the two markers?",
  },
  {
    label: "示例 C：探索环境关联",
    description: "检查一个类群与环境变量的统计关联及限制。",
    prompt: "Is the relative abundance of Syndiniales in V9 samples associated with nitrate plus nitrite? Report the sample size, the analysis method, and any important data limitations.",
  },
  {
    label: "示例 D：筛选样本",
    description: "用自然语言给出条件，核对匹配的样本。",
    prompt: "Which samples have a temperature of at most 10.2228 degrees Celsius? Return the sample IDs, sample count, and the data field used for filtering.",
  },
] as const;

const followUpPrompt = "Before interpreting the regional trends, inspect sequencing depth and sample counts for each ocean region in V4 and V9. Explain whether the current unrarefied diversity values are comparable and recommend an appropriate standardized analysis.";

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

      {variant === "auth" ? (
        <div className="project-intro-guide">
          <h3>{t("如何开始")}</h3>
          <ol>
            <li>{t("登录或以游客身份进入，选择一个示例问题。")}</li>
            <li>{t("尽量说明类群、V4/V9、海区或环境变量等分析范围。")}</li>
            <li>{t("查看结果图表、数据说明与执行链路，再继续追问。")}</li>
          </ol>
        </div>
      ) : null}

      {variant === "auth" ? (
        <details className="quick-tutorial-disclosure">
          <summary>{t("5 分钟上手 Tara Agent")}</summary>
          <QuickTutorial id="quick-tutorial-auth" />
        </details>
      ) : <QuickTutorial id="quick-tutorial-workspace" />}

      <nav className="project-intro-resources" aria-label={t("相关资源")}>
        <span>{t("相关资源")}：</span>
        {resources.map((resource) => (
          <a key={resource.name} href={resource.href} target="_blank" rel="noopener noreferrer"
            title={t(resource.description)}>
            {resource.name}<ArrowUpRight size={12} aria-hidden="true" />
            <span className="sr-only">{t("（在新标签页打开）")}</span>
          </a>
        ))}
      </nav>
    </section>
  );
}

function CopyPrompt({ prompt }: { prompt: string }) {
  const { t } = useLanguage();
  const [copied, setCopied] = useState(false);

  async function copy() {
    try {
      await navigator.clipboard.writeText(prompt);
      setCopied(true);
    } catch {
      setCopied(false);
    }
  }

  return (
    <button className="tutorial-copy" type="button" onClick={() => void copy()}>
      {copied ? <Check size={14} aria-hidden="true" /> : <Copy size={14} aria-hidden="true" />}
      {t(copied ? "已复制问题" : "复制问题")}
    </button>
  );
}

function QuickTutorial({ id }: { id: string }) {
  const { t } = useLanguage();

  return (
    <section className="quick-tutorial" aria-labelledby={id}>
      <h3 id={id}>{t("五步完成一次分析")}</h3>
      <ol className="tutorial-steps">
        <li>
          <h4>{t("1. 打开系统并开始对话")}</h4>
          <p>{t("访问 Tara Agent 正式站点，登录或以游客身份进入。")}</p>
          <a href="https://175.27.144.33/" target="_blank" rel="noopener noreferrer">https://175.27.144.33/</a>
          <p>{t("进入首页后，点击“新建对话”或选择一个示例问题。")}</p>
        </li>
        <li>
          <h4>{t("2. 用自然语言描述研究问题")}</h4>
          <p>{t("直接用科研语言提问，无需先写 SQL、Python 或记住数据表名。可以从下面四个问题开始：")}</p>
          <div className="tutorial-examples">
            {beginnerPrompts.map((item) => (
              <article className="tutorial-example" key={item.label}>
                <div className="tutorial-example-heading">
                  <strong>{t(item.label)}</strong>
                  <CopyPrompt prompt={item.prompt} />
                </div>
                <p>{t(item.description)}</p>
                <p className="tutorial-prompt" lang="en">{item.prompt}</p>
              </article>
            ))}
          </div>
          <p className="tutorial-note">{t("这些提示词用于尝试；能否完成取决于当前已接入的数据和工具，请以实际运行结果为准。")}</p>
        </li>
        <li>
          <h4>{t("3. 查看分析过程与链路")}</h4>
          <p>{t("提交后，展开“分析过程”；出现“查看链路”时可进一步检查执行详情。重点核对：")}</p>
          <ul>
            <li>{t("系统理解的问题是否与你的目标一致。")}</li>
            <li>{t("实际使用的数据、V4/V9 标记和环境变量是否正确。")}</li>
            <li>{t("每一步的状态、样本数、统计量和数据限制。")}</li>
          </ul>
          <p className="tutorial-note">{t("如果显示“部分完成”，应继续检查未完成的步骤，不能当作全部分析成功。")}</p>
        </li>
        <li>
          <h4>{t("4. 继续追问，完善分析")}</h4>
          <p>{t("例如完成 V4/V9 多样性比较后，可以继续问：")}</p>
          <div className="tutorial-example">
            <div className="tutorial-example-heading">
              <strong>{t("继续追问示例")}</strong>
              <CopyPrompt prompt={followUpPrompt} />
            </div>
            <p className="tutorial-prompt" lang="en">{followUpPrompt}</p>
          </div>
          <p className="tutorial-note">{t("若当前工具不能完成所需计算，应说明需要哪些外部工具，并区分已执行结果与尚未执行的建议。")}</p>
        </li>
        <li>
          <h4>{t("5. 保存研究上下文与结果")}</h4>
          <p>{t("会话历史可帮助回看问题和输出。重要研究还应另外保存数据及版本、筛选条件、方法参数、结果和限制；历史对话不等于完整的可复现分析档案。")}</p>
        </li>
      </ol>
    </section>
  );
}
