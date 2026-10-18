"use client";

import { createContext, type ReactNode, useContext, useMemo } from "react";
import { translateLabel, translateUi, type Language } from "@/lib/i18n";

const ResponseLanguageContext = createContext<Language>("zh");

export function ResponseLanguageProvider({ language, children }: { language: Language; children: ReactNode }) {
  return <ResponseLanguageContext.Provider value={language}>{children}</ResponseLanguageContext.Provider>;
}

// 结果内容与界面控件分别取语言，切换 UI 不会重新翻译已生成的结果。
export function useResponseLanguage() {
  const language = useContext(ResponseLanguageContext);
  return useMemo(() => ({
    language,
    label: (text: string) => translateLabel(text, language),
    t: (text: string, values?: Array<string | number>) => translateUi(text, language, values),
  }), [language]);
}
