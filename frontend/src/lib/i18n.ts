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
  const planningStep = /^确定第 (\d+) 步分析$/.exec(text);
  if (planningStep) return `Plan analysis step ${planningStep[1]}`;
  const completedStep = /^完成分析步骤 (\d+)$/.exec(text);
  if (completedStep) return `Analysis step ${completedStep[1]} completed`;
  return english[text] ?? text.replace(phrasePattern, (phrase) => english[phrase]);
}
