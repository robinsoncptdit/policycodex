// @ts-check
import { defineConfig } from 'astro/config';

export default defineConfig({
  // Set automatically by .github/workflows/build-handbook.yml from your
  // repo's Pages config. The literal fallback below only applies for local
  // builds without Pages enabled.
  site: process.env.ASTRO_SITE_URL || 'https://handbook.example.org',
});
