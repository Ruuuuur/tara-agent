import { strict as assert } from "node:assert";
import { test } from "node:test";
import { answerUiLabels } from "../src/lib/answer-ui-labels";

type Node = { type: string; value?: string; url?: string; children?: Node[] };

function fixture(): { type: string; children: Node[] } {
  return { type: "root", children: [
    { type: "paragraph", children: [
      { type: "text", value: "You can review outputs via “选择更多结果” at the end of this reply. " },
      { type: "strong", children: [{ type: "text", value: "选择更多结果" }] },
      { type: "text", value: " TARA_A100000038; Shannon=2.5; 北冰洋" },
    ] },
    { type: "code", value: "选择更多结果" },
    { type: "inlineCode", value: "选择更多结果" },
    { type: "html", value: '<span title="选择更多结果">raw</span>' },
    { type: "link", url: "https://example.com/选择更多结果", children: [{ type: "text", value: "Reference" }] },
  ] };
}

test("English answer normalizes quoted and bold app labels, preserving science, code, and link targets", () => {
  const original = fixture();
  const expected = fixture();
  expected.children[0].children![0].value = 'You can review outputs via “More results” at the end of this reply. ';
  expected.children[0].children![1].children![0].value = "More results";
  const actual = structuredClone(original);
  answerUiLabels({ language: "en" })(actual);
  assert.deepEqual(actual, expected);
  assert.equal(original.children[0].children![0].value?.includes("选择更多结果"), true);
});

test("Chinese answer retains its UI reference; English normalization is idempotent", () => {
  const original = fixture();
  const actual = structuredClone(original);
  answerUiLabels({ language: "zh" })(actual);
  assert.deepEqual(actual, original);
  answerUiLabels({ language: "en" })(actual);
  const normalized = structuredClone(actual);
  answerUiLabels({ language: "en" })(actual);
  assert.deepEqual(actual, normalized);
});
