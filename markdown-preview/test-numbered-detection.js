// Regression test for heading-number detection in lib/render-pdf.js.
// Run: node test-numbered-detection.js
const assert = require("node:assert");
const { hasManualHeadingNumbers } = require("./lib/render-pdf.js");

const numbered = [
  "## 1. Tesis ini tentang apa",
  "## 1.2 Latar Belakang",
  "### 1.2.1 Sub Pertama",
  "## I. Pendahuluan",
  "## BAB I PENDAHULUAN",
  "## 1) Tujuan",
  "#### 2.3.4 Metode",
];

const unnumbered = [
  "## Latar Belakang",
  "## Tujuan Penelitian",
  "## 2026 Outlook",
  "## 3D Printing",
  "## 4.5 juta pengguna", // bare number without punctuation after digits
  "## BAB tentang metode",
];

let failed = 0;
for (const h of numbered) {
  if (!hasManualHeadingNumbers(h)) {
    console.log(`FAIL  expected numbered:   ${h}`);
    failed++;
  }
}
for (const h of unnumbered) {
  if (hasManualHeadingNumbers(h)) {
    console.log(`FAIL  expected unnumbered: ${h}`);
    failed++;
  }
}

if (failed === 0) {
  console.log(`PASS  ${numbered.length + unnumbered.length} heading cases`);
}
process.exit(failed === 0 ? 0 : 1);
