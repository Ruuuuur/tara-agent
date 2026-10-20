import type { Language } from "./i18n";

// 只翻译程序生成的未鉴定前缀；鉴定状态和完整模板都匹配时才处理。
export function taxonomyCellValue(column: string, row: Record<string, unknown>, language: Language): unknown {
  const value = row[column];
  if (language !== "en" || column !== "taxon_label" || row.classification_status !== "unresolved"
    || typeof value !== "string") return value;
  const match = /^未鉴定到(属|种)（([\s\S]*)）$/.exec(value);
  if (!match) return value;
  return `Unresolved ${match[1] === "属" ? "genus" : "species"} (${match[2]})`;
}
