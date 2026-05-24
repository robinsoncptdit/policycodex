#!/usr/bin/env node
/**
 * Verify that `npm run build` produced a usable handbook:
 *   - dist/index.html exists and is non-trivial
 *   - at least one policy page exists (any non-trivial index.html under
 *     dist/policies/, at any depth - flat policies and bundles both count)
 * Generic across dioceses: no policy slugs are hardcoded.
 */
import { existsSync, readFileSync, readdirSync } from 'node:fs';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const dist = join(__dirname, '..', 'dist');

const MIN_BYTES = 100;
let failed = 0;

function checkFile(rel) {
  const full = join(dist, rel);
  if (!existsSync(full)) {
    console.error(`MISSING: dist/${rel}`);
    return false;
  }
  if (readFileSync(full, 'utf-8').length < MIN_BYTES) {
    console.error(`TOO SMALL: dist/${rel}`);
    return false;
  }
  return true;
}

// 1. Home page.
if (checkFile('index.html')) {
  console.log('OK: dist/index.html');
} else {
  failed += 1;
}

// 2. At least one policy page anywhere under dist/policies/.
function* walkIndexHtml(dir) {
  if (!existsSync(dir)) return;
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    const full = join(dir, entry.name);
    if (entry.isDirectory()) {
      yield* walkIndexHtml(full);
    } else if (entry.name === 'index.html') {
      yield full;
    }
  }
}

let policyPages = 0;
for (const page of walkIndexHtml(join(dist, 'policies'))) {
  if (readFileSync(page, 'utf-8').length >= MIN_BYTES) {
    policyPages += 1;
  }
}
if (policyPages >= 1) {
  console.log(`OK: ${policyPages} policy page(s)`);
} else {
  console.error('No non-trivial policy pages found under dist/policies/');
  failed += 1;
}

if (failed > 0) {
  console.error(`\n${failed} check(s) failed.`);
  process.exit(1);
}
console.log('\nBuild verification passed.');
process.exit(0);
