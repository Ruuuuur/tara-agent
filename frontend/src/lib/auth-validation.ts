export type AuthField = "email" | "password" | "display_name";
type Translate = (text: string, values?: Array<string | number>) => string;

export function authValidationMessage(
  field: AuthField,
  input: Pick<HTMLInputElement, "value" | "validity" | "minLength" | "maxLength">,
  t: Translate,
): string {
  const label = { email: "邮箱", password: "密码", display_name: "昵称" }[field];
  if (input.validity.valueMissing) return t(`请输入${label}`);
  if (field === "display_name" && !input.value.trim()) return t("昵称不能为空");
  if (field === "email" && input.validity.typeMismatch) return t("请输入正确的邮箱地址");
  // 自动填充和脚本填值不一定触发浏览器的 tooShort；按服务端口径计算字符数。
  const length = Array.from(input.value).length;
  if (input.validity.tooShort || (input.minLength > 0 && length < input.minLength)) {
    return t(`${label}至少需要 {0} 个字符`, [input.minLength]);
  }
  if (input.validity.tooLong || (input.maxLength >= 0 && length > input.maxLength)) {
    return t(`${label}最多允许 {0} 个字符`, [input.maxLength]);
  }
  return "";
}
