
"use client";

import { useResponseLanguage } from "@/components/response-language-provider";
import { useLanguage } from "@/components/language-provider";
import { sourceGroups } from "@/lib/trace-data-summary";

export function ArtifactHeading({ title, scope, sources, prefix = "" }: {
  title: string; scope: string; sources: string[]; prefix?: string;
}) {
  const { label } = useResponseLanguage();
  return (
    <span className="artifact-heading">
      <span className="artifact-heading-title">{prefix}{label(title)}</span>
      {scope ? <span className="artifact-heading-scope">{label(scope)}</span> : null}
      <DataSourceList sources={sources} />
    </span>
  );
}

export function DataSourceList({ sources }: { sources: string[] }) {
  const { t } = useLanguage();
  const groups = sourceGroups(sources);
  return (
    <span className="source-groups">
      {groups.length ? groups.map((group) => (
        <span className="source-files" key={group.label}>
          <span className="source-files-label">{t(group.label)} ({group.files.length})</span>
          <span className="source-files-list">
            {group.files.map((name) => <code key={name}>{name}</code>)}
          </span>
        </span>
      )) : <span>{t("数据来源未记录")}</span>}
    </span>
  );
}
