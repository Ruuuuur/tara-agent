import { english } from "./ui-translations";

export type Language = "zh" | "en";

const phrases = Object.keys(english).filter((key) => !key.includes("{0}"))
  .sort((left, right) => right.length - left.length);
function escapePattern(text: string): string {
  return text.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

const phrasePattern = new RegExp(phrases.map(escapePattern).join("|"), "g");
const numericMessages = Object.entries(english)
  .filter(([source]) => source.includes("{0}") && !source.includes("{1}"))
  .map(([source, target]) => ({
    pattern: new RegExp(`^${source.split("{0}").map(escapePattern).join("(\\d+)")}$`),
    target,
  }));

function translateMessage(text: string): string {
  if (english[text]) return english[text];
  // 只识别词典内的完整数值模板，避免改写未知错误中的科学内容和标识。
  for (const { pattern, target } of numericMessages) {
    const match = pattern.exec(text);
    if (match) return target.replace("{0}", match[1]);
  }
  return text;
}

export function translateUi(text: string, language: Language, values: Array<string | number> = []): string {
  const template = language === "en" ? text.split("\n").map(translateMessage).join("\n") : text;
  return template.replace(/\{(\d+)\}/g, (match, index) => String(values[Number(index)] ?? match));
}

export function translateLabel(text: string, language: Language): string {
  // 仅供应用组合的标题和摘要使用；未知错误、正文和数据值不做片段替换。
  if (language === "zh") return text;
  // 先翻译完整标题，再递归处理应用生成的步骤、角色与表格后缀，避免片段混译和粘连。
  if (english[text]) return english[text];
  const artifactStep = /^步骤 (\d+) · ([\s\S]+)$/.exec(text);
  if (artifactStep) return `Step ${artifactStep[1]} · ${translateLabel(artifactStep[2], language)}`;
  const artifactRole = /^(【中间步骤结果】|【最终结果】)([\s\S]+)$/.exec(text);
  if (artifactRole) return `${english[artifactRole[1]].trimEnd()} ${translateLabel(artifactRole[2], language)}`;
  if (text.endsWith("表") && english[text.slice(0, -1)]) {
    const title = english[text.slice(0, -1)];
    return /\btable$/i.test(title) ? title : `${title} table`;
  }
  const parts = text.split(" · ");
  if (parts.length > 1) return parts.map((part) => translateLabel(part, language)).join(" · ");
  const latitude = /^(.+)随纬度变化$/.exec(text);
  if (latitude) return `${translateLabel(latitude[1], language)} vs latitude`;
  const surface = /^(.+ μm)表层群落相对丰度$/.exec(text);
  if (surface) return `Surface community relative abundance (${surface[1]})`;
  const topFunctions = /^Top (\d+) 功能相对转录贡献$/.exec(text);
  if (topFunctions) return `Top ${topFunctions[1]} functions by relative transcript contribution`;
  const allocation = /^Top (\d+) 功能(粒径|海区)分配$/.exec(text);
  if (allocation) return `Top ${allocation[1]} function allocation by ${allocation[2] === "粒径" ? "size fraction" : "ocean region"}`;
  const plsCircle = /^(.+) 环境PLS相关圆（(\d+)组）$/.exec(text);
  if (plsCircle) return `${translateLabel(plsCircle[1], language)} environmental PLS correlation circle (${plsCircle[2]} groups)`;
  const pls = /^环境PLS（(\d+)组）$/.exec(text);
  if (pls) return `Environmental PLS (${pls[1]} groups)`;
  const nmds = /^四粒径NMDS（Stress1=([^）]+)）$/.exec(text);
  if (nmds) return `Four-size-fraction NMDS (Stress1=${nmds[1]})`;
  const functionSignal = /^(.+)与(PF\d+)( (?:MetaG|MetaT))信号$/.exec(text);
  if (functionSignal) return `${translateLabel(functionSignal[1], language)} vs ${functionSignal[2]}${functionSignal[3]} signal`;
  const abundance = /^(.+) 与相对丰度$/.exec(text);
  if (abundance) return `${translateLabel(abundance[1], language)} vs relative abundance`;
  const familySignal = /^(.+) 采样编码对应的相对功能信号$/.exec(text);
  if (familySignal) return `Relative functional signal for matched sampling codes: ${familySignal[1]}`;
  const planningStep = /^确定第 (\d+) 步分析$/.exec(text);
  if (planningStep) return `Plan analysis step ${planningStep[1]}`;
  const completedStep = /^完成分析步骤 (\d+)$/.exec(text);
  if (completedStep) return `Analysis step ${completedStep[1]} completed`;
  return english[text] ?? text.replace(phrasePattern, (phrase) => english[phrase]);
}
