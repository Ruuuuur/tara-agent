const fieldLabels: Record<string, string> = {
  email: "邮箱", password: "密码", display_name: "昵称", question: "问题", title: "会话名称",
};

function record(value: unknown): Record<string, unknown> | undefined {
  return value !== null && typeof value === "object" && !Array.isArray(value)
    ? value as Record<string, unknown> : undefined;
}

function validationMessage(value: unknown): string {
  const issue = record(value);
  const location = Array.isArray(issue?.loc) ? issue.loc : [];
  const field = location.length === 2 && location[0] === "body" ? String(location[1]) : "";
  const label = fieldLabels[field];
  if (!issue || !label) return "请求参数无效，请检查输入。";
  if (issue.type === "missing") return `请输入${label}`;
  if (field === "email") return "请输入正确的邮箱地址";
  if (field === "display_name" && issue.type === "value_error") return "昵称不能为空";
  const context = record(issue.ctx);
  if (issue.type === "string_too_short" && typeof context?.min_length === "number") {
    return `${label}至少需要 ${context.min_length} 个字符`;
  }
  if (issue.type === "string_too_long" && typeof context?.max_length === "number") {
    return `${label}最多允许 ${context.max_length} 个字符`;
  }
  return "请求参数无效，请检查输入。";
}

export function apiErrorMessage(payload: unknown, status: number): string {
  const detail = record(payload)?.detail;
  if (typeof detail === "string" && detail.trim()) return detail;
  if (Array.isArray(detail) && detail.length) {
    // 只提取已知字段与约束，不回显校验错误中的密码、原始输入或调试上下文。
    return [...new Set(detail.map(validationMessage))].join("\n");
  }
  return `请求失败（HTTP ${status}）`;
}
