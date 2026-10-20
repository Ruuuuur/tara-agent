export type AnswerQuote = { text: string; traceId?: string };

const quoteLimit = 700;
const quoteHeader = /^引用此前回答(?:（Trace ID: ([0-9a-f-]{36})）)?：\n/i;
const followUpSeparator = "\n\n我的追问：";

export function quotePreview(text: string, limit: number): string {
  const plain = text.replace(/^#{1,6}\s+/gm, "").replace(/[*_`]/g, "").replace(/\s+/g, " ").trim();
  return plain.length > limit ? `${plain.slice(0, limit)}…` : plain;
}

export function formatQuotedQuestion(question: string, quote: AnswerQuote | null): string {
  const prompt = question.trim();
  if (!quote) return prompt;
  const excerpt = quote.text.trim().slice(0, quoteLimit);
  const reference = quote.traceId ? `（Trace ID: ${quote.traceId}）` : "";
  const block = excerpt.split(/\r?\n/).map((line) => `> ${line}`).join("\n");
  return `引用此前回答${reference}：\n${block}${followUpSeparator}${prompt}`;
}

export function parseQuotedQuestion(value: string): { question: string; quote: AnswerQuote } | null {
  const header = value.match(quoteHeader);
  if (!header) return null;
  const splitAt = value.lastIndexOf(followUpSeparator);
  if (splitAt < header[0].length) return null;
  const block = value.slice(header[0].length, splitAt);
  const lines = block.split("\n");
  if (!lines.length || lines.some((line) => !line.startsWith("> "))) return null;
  return {
    question: value.slice(splitAt + followUpSeparator.length),
    quote: { text: lines.map((line) => line.slice(2)).join("\n"), traceId: header[1] },
  };
}
