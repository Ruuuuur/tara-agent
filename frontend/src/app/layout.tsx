import type { Metadata } from "next";
import type { ReactNode } from "react";

import { LanguageProvider } from "@/components/language-provider";
import { AuthGate } from "@/components/auth-gate";

import "./globals.css";

export const metadata: Metadata = {
  title: "Tara Agent",
  description: "Tara Agent",
};

export default function RootLayout({ children }: Readonly<{ children: ReactNode }>) {
  return (
    <html lang="zh-CN">
      <body><LanguageProvider><AuthGate>{children}</AuthGate></LanguageProvider></body>
    </html>
  );
}
