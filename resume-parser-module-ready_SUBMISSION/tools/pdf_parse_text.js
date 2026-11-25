const fs = require('fs');
const pdf = require('pdf-parse');

async function main() {
  const args = process.argv.slice(2);
  if (args.length === 0) {
    const buffer = fs.readFileSync(0);
    try {
      const result = await pdf(buffer);
      process.stdout.write(result?.text?.trim() || '');
      process.exit(0);
    } catch (err) {
      process.stderr.write((err && err.message) || String(err));
      process.exit(1);
    }
  }

  if (args[0] === '--batch') {
    const fileListPath = args[1];
    const outPath = args[2];
    const files = JSON.parse(fs.readFileSync(fileListPath, 'utf8'));
    const results = {};
    for (const f of files) {
      try {
        const buffer = fs.readFileSync(f);
        const result = await pdf(buffer);
        results[f] = result?.text?.trim() || '';
      } catch (err) {
        results[f] = null;
      }
    }
    const jsonStr = JSON.stringify(results);
    if (outPath) {
      fs.writeFileSync(outPath, jsonStr, 'utf8');
    } else {
      process.stdout.write(jsonStr);
    }
    process.exit(0);
  }

  // Single file mode
  try {
    const buffer = fs.readFileSync(args[0]);
    const result = await pdf(buffer);
    process.stdout.write(result?.text?.trim() || '');
    process.exit(0);
  } catch (err) {
    process.stderr.write((err && err.message) || String(err));
    process.exit(1);
  }
}

main();
