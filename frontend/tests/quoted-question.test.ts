import { strict as assert } from "node:assert";
import { test } from "node:test";

import { formatQuotedQuestion, parseQuotedQuestion } from "../src/lib/quoted-question";

test("a quoted follow-up keeps the question separate for compact display and history", () => {
  const quote = {
    text: "Temperature is negatively associated with abundance.\nCheck the sample count.",
    traceId: "4f9291a0-883e-4d10-a7fa-e69518c18ba1",
  };
  const submitted = formatQuotedQuestion("请按海区重算，说明样本数。", quote);
  assert.deepEqual(parseQuotedQuestion(submitted), {
    question: "请按海区重算，说明样本数。",
    quote,
  });
});

test("ordinary questions do not acquire a quote", () => {
  assert.equal(formatQuotedQuestion("  普通问题  ", null), "普通问题");
  assert.equal(parseQuotedQuestion("普通问题"), null);
});
