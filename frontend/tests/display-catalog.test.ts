import { strict as assert } from "node:assert";
import { test } from "node:test";
import { readFileSync, readdirSync } from "node:fs";
import { join } from "node:path";
import ts from "typescript";
import { translateLabel, translateUi } from "../src/lib/i18n";
import { resultCellValue } from "../src/lib/result-cell-value";
import { processPresentation } from "../src/lib/process-presentation";
import { artifactTitle } from "../src/lib/artifact-presentation";
import catalog from "./fixtures/backend-display-messages.json";

// 目录直接采集后端源码；新增固定状态/错误必须有对应英文，避免仅覆盖截图。
test("all captured runtime statuses, tool titles, axes and errors have complete English displays", () => {
  const saved = structuredClone(catalog);
  for (const {kind, text} of catalog) {
    const shown = ["reason", "output"].includes(kind)
      ? resultCellValue(kind, {[kind]: text}, "en")
      : ["error", "detail"].includes(kind) ? translateUi(text, "en")
        : translateLabel(artifactTitle(processPresentation({stage: "answer", title: text, detail: ""}).title), "en");
    assert.equal(typeof shown, "string", `${kind}: ${text}`);
    assert.doesNotMatch(String(shown), /[\u3400-\u9fff]/, `${kind}: ${text}`);
  }
  assert.deepEqual(catalog, saved);
});

test("static UI translation calls and literal JSX text cannot silently ship untranslated Chinese", () => {
  const walk = (directory: string): string[] => readdirSync(directory, {withFileTypes: true})
    .flatMap(entry => entry.isDirectory() ? walk(join(directory, entry.name)) : [join(directory, entry.name)]);
  for (const file of walk(join(process.cwd(), "src")).filter(file => /\.tsx?$/.test(file))) {
    const source = ts.createSourceFile(file, readFileSync(file, "utf8"), ts.ScriptTarget.Latest, true);
    const visit = (node: ts.Node) => {
      if (ts.isStringLiteral(node) || ts.isNoSubstitutionTemplateLiteral(node)) {
        const parent = node.parent;
        if (ts.isCallExpression(parent) && ts.isIdentifier(parent.expression)
          && ["t", "contentText"].includes(parent.expression.text) && parent.arguments[0] === node) {
          assert.doesNotMatch(translateUi(node.text, "en", [1, 2, 3]), /[\u3400-\u9fff]/, `${file}: ${node.text}`);
        }
      }
      if (ts.isJsxAttribute(node) && node.initializer && ts.isStringLiteral(node.initializer)) {
        assert.doesNotMatch(node.initializer.text, /[\u3400-\u9fff]/, `${file}: literal JSX attribute`);
      }
      if (ts.isJsxText(node)) assert.doesNotMatch(node.text.trim(), /[\u3400-\u9fff]/, `${file}: literal JSX text`);
      ts.forEachChild(node, visit);
    };
    visit(source);
  }
});

test("unknown data and object-property names are preserved by both exact translators", () => {
  for (const text of ["constructor", "toString", "__proto__", "未知诊断 PF00069 0.25"]) {
    assert.equal(translateUi(text, "en"), text);
    assert.equal(translateLabel(text, "en"), text);
  }
});
