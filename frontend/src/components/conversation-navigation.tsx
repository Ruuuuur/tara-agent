"use client";

import { useLanguage } from "@/components/language-provider";

import { ArrowDown, ArrowUp, List } from "lucide-react";
import { useEffect, useId, useRef, useState } from "react";

import { formatDateTime } from "@/lib/format";

type ConversationNavigationProps = {
  items: { id: string; question: string; createdAt: string }[];
  onNavigate: (target: "top" | "bottom" | { id: string }) => void;
};

export function ConversationNavigation({ items, onNavigate }: ConversationNavigationProps) {
  const { t } = useLanguage();
  const [open, setOpen] = useState(false);
  const panelId = useId();
  const navigationRef = useRef<HTMLElement>(null);
  const indexButtonRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (!open) return;
    function closeOutside(event: PointerEvent) {
      if (event.target instanceof Node && !navigationRef.current?.contains(event.target)) {
        setOpen(false);
      }
    }
    document.addEventListener("pointerdown", closeOutside);
    return () => document.removeEventListener("pointerdown", closeOutside);
  }, [open]);

  function navigate(target: Parameters<ConversationNavigationProps["onNavigate"]>[0]) {
    setOpen(false);
    onNavigate(target);
  }

  return (
    <nav ref={navigationRef} className="conversation-navigation" aria-label={t("对话导航")}
      onKeyDown={(event) => {
        if (event.key === "Escape" && open) {
          event.stopPropagation();
          setOpen(false);
          indexButtonRef.current?.focus();
        }
      }}>
      <button type="button" title={t("回到顶部")} aria-label={t("回到顶部")}
        onClick={() => navigate("top")}><ArrowUp size={17} aria-hidden="true" /></button>
      <button ref={indexButtonRef} type="button" title={t("提问索引（{0} 条）", [items.length])}
        aria-label={t("提问索引，共 {0} 条", [items.length])} aria-expanded={open} aria-controls={panelId}
        onClick={() => setOpen((current) => !current)}><List size={17} aria-hidden="true" /></button>
      {open ? (
        <section id={panelId} className="prompt-index" aria-label={t("本次对话的提问索引")}>
          <div className="prompt-index-heading">{t("提问索引")}<span>{items.length} {t("条")}</span></div>
          <ol>
            {items.map((item, index) => (
              <li key={item.id}>
                <button type="button" title={item.question}
                  onClick={() => navigate({ id: item.id })}>
                  <span className="prompt-index-number">{index + 1}</span>
                  <span className="prompt-index-content">
                    <span>{item.question}</span>
                    <time dateTime={item.createdAt}>{formatDateTime(item.createdAt)}</time>
                  </span>
                </button>
              </li>
            ))}
          </ol>
        </section>
      ) : null}
      <button type="button" title={t("回到底部并跟随新回答")} aria-label={t("回到底部并跟随新回答")}
        onClick={() => navigate("bottom")}><ArrowDown size={17} aria-hidden="true" /></button>
    </nav>
  );
}
