"use client";

import { Languages } from "lucide-react";
import { createContext, type ReactNode, useCallback, useContext, useEffect, useState } from "react";
import { translateLabel, translateUi, type Language } from "@/lib/i18n";

const storageKey = "tara-interface-language";
const LanguageContext = createContext<{
  language: Language;
  setLanguage: (language: Language) => void;
  label: (text: string) => string;
  t: (text: string, values?: Array<string | number>) => string;
} | null>(null);

export function LanguageProvider({ children }: { children: ReactNode }) {
  // 首次渲染沿用中文，确保服务端页面与 hydration 一致。
  const [language, updateLanguage] = useState<Language>("zh");
  const setLanguage = useCallback((next: Language) => {
    document.documentElement.lang = next === "en" ? "en" : "zh-CN";
    updateLanguage(next);
    try { localStorage.setItem(storageKey, next); } catch { /* 禁用存储时仍允许当次切换。 */ }
  }, []);

  useEffect(() => {
    const restore = () => {
      try {
        const saved = localStorage.getItem(storageKey);
        if (saved === "en" || saved === "zh") setLanguage(saved);
      } catch { /* 浏览器禁用存储时使用默认语言。 */ }
    };
    restore();
    const sync = (event: StorageEvent) => {
      if (event.key === storageKey) restore();
    };
    window.addEventListener("storage", sync);
    return () => window.removeEventListener("storage", sync);
  }, [setLanguage]);

  const t = useCallback((text: string, values?: Array<string | number>) => translateUi(text, language, values), [language]);
  const label = useCallback((text: string) => translateLabel(text, language), [language]);
  return <LanguageContext.Provider value={{ language, setLanguage, t, label }}>{children}</LanguageContext.Provider>;
}

export function useLanguage() {
  const context = useContext(LanguageContext);
  if (!context) throw new Error("useLanguage 必须在 LanguageProvider 内使用");
  return context;
}

export function LanguageToggle() {
  const { language, setLanguage } = useLanguage();
  const label = language === "zh" ? "Switch to English" : "切换为中文";
  return (
    <button className="language-toggle" type="button" title={label} aria-label={label}
      lang={language === "zh" ? "en" : "zh-CN"}
      onClick={() => setLanguage(language === "zh" ? "en" : "zh")}>
      <Languages size={16} aria-hidden="true" />
      <span>{language === "zh" ? "English" : "中文"}</span>
    </button>
  );
}
