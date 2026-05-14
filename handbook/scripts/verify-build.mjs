#!/usr/bin/env node
/**
 * Verify that `npm run build` produced the expected static files.
 * Used in place of a unit-test runner for the Astro proof.
 */
import { existsSync, readFileSync } from 'node:fs';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const dist = join(__dirname, '..', 'dist');

const expected = [
  'index.html',
  'policies/onboarding/index.html',
  'policies/code-of-conduct/index.html',
  'policies/retention/index.html',
];

let failed = 0;
for (const rel of expected) {
  const full = join(dist, rel);
  if (!existsSync(full)) {
    console.error(`MISSING: dist/${rel}`);
    failed += 1;
    continue;
  }
  const html = readFileSync(full, 'utf-8');
  if (html.length < 100) {
    console.error(`TOO SMALL: dist/${rel} (${html.length} bytes)`);
    failed += 1;
    continue;
  }
  console.log(`OK: dist/${rel} (${html.length} bytes)`);
}

if (failed > 0) {
  console.error(`\n${failed} expected file(s) missing or empty.`);
  process.exit(1);
}
console.log(`\nAll ${expected.length} expected files present.`);
process.exit(0);
