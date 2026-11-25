/**
 * tools/pdf_text.js
 * Option B Prototype: Standalone Node.js CLI script for PDF text extraction.
 *
 * Contains a verbatim copy of `extractTextWithPdfJs` from `src/extractResumeText.ts` (lines 86-132)
 * and `normalizeResumeText` (lines 24-31).
 */
const fs = require('fs');

// Verbatim copy from src/extractResumeText.ts (lines 24-31)
function normalizeResumeText(raw) {
  return raw
    .replace(/\r\n/g, '\n')
    .replace(/\r/g, '\n')
    .replace(/[ \t]+\n/g, '\n')
    .replace(/\n{3,}/g, '\n\n')
    .trim();
}

// Verbatim copy from src/extractResumeText.ts (lines 86-132)
async function extractTextWithPdfJs(buffer) {
  try {
    const pdfjs = await import('pdfjs-dist/legacy/build/pdf.mjs');
    const loadingTask = pdfjs.getDocument({
      data: new Uint8Array(buffer),
      disableWorker: true,
      useSystemFonts: true,
      isEvalSupported: false,
    });
    const doc = await loadingTask.promise;
    let allText = '';
    for (let i = 1; i <= doc.numPages; i += 1) {
      const page = await doc.getPage(i);
      const content = await page.getTextContent();
      let lastY = null;
      let pageText = '';
      for (const item of content.items) {
        const str = item.str || '';
        if (!str) continue;
        const currentY = typeof item.transform?.[5] === 'number' ? item.transform[5] : null;
        if (lastY !== null && currentY !== null && Math.abs(currentY - lastY) > 4) {
          pageText += '\n';
        } else if (pageText.length > 0 && !pageText.endsWith('\n') && !pageText.endsWith(' ')) {
          pageText += ' ';
        }
        pageText += str;
        if (item.hasEOL) {
          pageText += '\n';
        }
        if (currentY !== null) {
          lastY = currentY;
        }
      }
      allText += pageText + '\n\n';
    }
    return normalizeResumeText(allText);
  } catch {
    return '';
  }
}

async function main() {
  const filePath = process.argv[2];
  let buffer;
  if (filePath) {
    buffer = fs.readFileSync(filePath);
  } else {
    buffer = fs.readFileSync(0); // stdin
  }
  const text = await extractTextWithPdfJs(buffer);
  process.stdout.write(text);
}

main().catch(err => {
  process.stderr.write(String(err));
  process.exit(1);
});

