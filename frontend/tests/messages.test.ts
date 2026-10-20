import { strict as assert } from "node:assert";
import { test } from "node:test";

import { readApiError } from "../src/lib/api";
import { apiErrorMessage } from "../src/lib/api-error-detail";
import { authValidationMessage } from "../src/lib/auth-validation";
import { translateUi } from "../src/lib/i18n";

for (const [source, expected] of [
  ["模型返回了无效的分析决定", "The model could not produce a valid analysis plan. Please try again."],
  ["模型服务暂时不可用，请稍后重试。", "The model service is temporarily unavailable. Please try again later."],
  ["示例问题暂时不可用，请检查处理后数据。", "Example questions are temporarily unavailable. Please check the processed data."],
  ["请求来源不受信任。", "This request comes from an untrusted origin."],
  ["该邮箱已经注册。", "This email address is already registered."],
  ["邮箱或密码不正确。", "Incorrect email address or password."],
  ["游客登录未开放。", "Guest sign-in is disabled."],
  ["认证服务不可用。", "The authentication service is unavailable."],
]) {
  test(`API message can switch languages: ${source}`, async () => {
    const error = await readApiError(new Response(JSON.stringify({ detail: source }), { status: 403 }));
    assert.equal(translateUi(error.message, "en"), expected);
    assert.equal(translateUi(error.message, "zh"), source);
    assert.equal(error.status, 403);
  });
}

test("registration validation returns readable localized messages without echoing inputs", async () => {
  const error = await readApiError(new Response(JSON.stringify({ detail: [
    { loc: ["body", "email"], type: "value_error", msg: "value is not a valid email address", input: "bad-email" },
    { loc: ["body", "password"], type: "string_too_short", ctx: { min_length: 12 }, input: "never-display-this-password" },
    { loc: ["body", "display_name"], type: "value_error", msg: "Value error, 昵称不能为空", input: " " },
  ] }), { status: 422 }));
  assert.equal(translateUi(error.message, "en"), "Enter a valid email address\nPassword must contain at least 12 characters.\nThe display name cannot be blank.");
  assert.equal(translateUi(error.message, "zh"), "请输入正确的邮箱地址\n密码至少需要 12 个字符\n昵称不能为空");
  assert.ok(!error.message.includes("never-display-this-password"));
  assert.ok(!error.message.includes("[object Object]"));
});

test("validation messages handle length constraints, unknown fields and malformed responses", () => {
  const message = apiErrorMessage({ detail: [
    { loc: ["body", "display_name"], type: "missing" },
    { loc: ["body", "password"], type: "string_too_long", ctx: { max_length: 128 } },
    { loc: ["query", "limit"], type: "int_parsing", input: "private-input" },
  ] }, 422);
  assert.equal(translateUi(message, "en"), "Enter your display name\nPassword must contain no more than 128 characters.\nInvalid request parameters. Please check your input.");
  assert.equal(translateUi(apiErrorMessage(null, 502), "en"), "Request failed (HTTP 502)");
  assert.equal(translateUi(apiErrorMessage({ detail: { unexpected: true } }, 500), "en"), "Request failed (HTTP 500)");
});

test("unknown scientific diagnostics are preserved exactly", () => {
  const source = "未知科学错误：硅藻 PF00001 相对信号 0.02；请求来源不受信任。";
  assert.equal(translateUi(source, "en"), source);
  assert.equal(translateUi("下载{0}", "en", ["原始样本.csv"]), "Download 原始样本.csv");
});

for (const [field, source, expected] of [
  ["email", "请输入邮箱", "Enter your email"],
  ["password", "请输入密码", "Enter your password"],
  ["display_name", "请输入昵称", "Enter your display name"],
] as const) {
  test(`native validation follows interface language: ${field}`, () => {
    const input = { value: "", minLength: 12, maxLength: 128,
      validity: { valueMissing: true } as ValidityState };
    assert.equal(authValidationMessage(field, input, (text, values) => translateUi(text, "en", values)), expected);
    assert.equal(authValidationMessage(field, input, (text, values) => translateUi(text, "zh", values)), source);
  });
}

test("native password length and blank display name receive explicit translations", () => {
  const t = (text: string, values?: Array<string | number>) => translateUi(text, "en", values);
  assert.equal(authValidationMessage("password", { value: "short", minLength: 12, maxLength: 128,
    validity: {} as ValidityState }, t), "Password must contain at least 12 characters.");
  assert.equal(authValidationMessage("display_name", { value: "  ", minLength: 1, maxLength: 80,
    validity: {} as ValidityState }, t), "The display name cannot be blank.");
});
