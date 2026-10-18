import type { Language } from "./i18n";

// 展示语言取自本轮保存的回答，绝不取自界面开关；旧会话也能稳定恢复。
export function responseLanguage(answer: string, question = ""): Language {
  for (const text of [answer, question]) {
    const prose = text.replace(/```[\s\S]*?```|`[^`]*`/g, "");
    const chinese = prose.match(/[\u3400-\u9fff]/g)?.length ?? 0;
    const english = prose.match(/[A-Za-z]+/g)?.length ?? 0;
    if (chinese || english) return chinese * 2 > english ? "zh" : "en";
  }
  return "zh";
}
