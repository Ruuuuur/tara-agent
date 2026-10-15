"use client";

import { useLanguage } from "@/components/language-provider";

import { AlertTriangle, LoaderCircle } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { getTrace } from "@/lib/api";

export function LegacyTraceRedirect({ traceId }: { traceId: string }) {
  const { t } = useLanguage();
  const router = useRouter();
  const [error, setError] = useState<string>();

  useEffect(() => {
    const controller = new AbortController();
    getTrace(traceId, controller.signal)
      .then((trace) => {
        router.replace(`/sessions/${encodeURIComponent(trace.session_id)}/traces/${encodeURIComponent(trace.id)}`);
      })
      .catch((reason: unknown) => {
        if (!(reason instanceof DOMException && reason.name === "AbortError")) {
          setError(reason instanceof Error ? reason.message : "无法打开链路记录");
        }
      });
    return () => controller.abort();
  }, [router, traceId]);

  return (
    <main className="trace-redirect-state">
      {error ? <><AlertTriangle size={20} /><span>{t(error)}</span></> : <><LoaderCircle className="spin" size={20} /><span>{t("正在打开链路…")}</span></>}
    </main>
  );
}
