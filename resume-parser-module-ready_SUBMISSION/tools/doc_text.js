/**
 * tools/doc_text.js
 * Option B Prototype: Standalone Node.js CLI script for DOC text extraction using word-extractor.
 *
 * Contains a verbatim copy of the DOC extraction logic in `src/extractResumeText.ts` (lines 189-195)
 * and `normalizeResumeText` (lines 24-31).
 */
const fs = require('fs');
const WordExtractor = require('word-extractor');

// Verbatim copy from src/extractResumeText.ts (lines 24-31)
function normalizeResumeText(raw) {
  return raw
    .replace(/\r\n/g, '\n')
    .replace(/\r/g, '\n')
    .replace(/[ \t]+\n/g, '\n')
    .replace(/\n{3,}/g, '\n\n')
    .trim();
}

async function extractTextWithWordExtractor(buffer) {
  const extractor = new WordExtractor();
  const doc = await extractor.extract(buffer);
  const text = normalizeResumeText(doc.getBody() || '');
  return text;
}

async function main() {
  const filePath = process.argv[2];
  let buffer;
  if (filePath) {
    buffer = fs.readFileSync(filePath);
  } else {
    buffer = fs.readFileSync(0); // stdin
  }
  const text = await extractTextWithWordExtractor(buffer);
  process.stdout.write(text);
}

main().catch(err => {
  process.stderr.write(String(err && err.message ? err.message : err));
  process.exit(1);
});

