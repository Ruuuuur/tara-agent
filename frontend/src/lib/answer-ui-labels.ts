import type { Language } from "./i18n";

type MarkdownNode = { type?: string; value?: string; children?: MarkdownNode[] };

// 仅规范正文里应用自身的固定入口名；不重写回答、代码或原始科学数据。
export function answerUiLabels({ language }: { language: Language }) {
  return (tree: unknown) => {
    if (language !== "en") return;
    function visit(node: MarkdownNode) {
      if (["code", "inlineCode", "html"].includes(node.type ?? "")) return;
      if (node.type === "text" && typeof node.value === "string") {
        node.value = node.value.replaceAll("选择更多结果", "More results");
      }
      for (const child of node.children ?? []) visit(child);
    }
    visit(tree as MarkdownNode);
  };
}
