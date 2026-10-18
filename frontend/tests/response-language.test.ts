import assert from "node:assert/strict";
import test from "node:test";
import { responseLanguage } from "../src/lib/response-language";

test("saved response language takes priority over the question and UI", () => {
  assert.equal(responseLanguage("The samples have different abundance distributions.", "请分析样本"), "en");
  assert.equal(responseLanguage("这些样本的丰度分布不同。", "Compare the samples"), "zh");
  assert.equal(responseLanguage("The sample belongs to Atlantic Ocean（大西洋） and was collected at the surface.", "请分析"), "en");
});

test("code and empty answers do not override the response prose or question", () => {
  assert.equal(responseLanguage("```python\n# 中文注释\n```\nThe analysis is complete."), "en");
  assert.equal(responseLanguage("", "Compare the samples"), "en");
  assert.equal(responseLanguage("", "比较这些样本"), "zh");
  assert.equal(responseLanguage("", ""), "zh");
});
