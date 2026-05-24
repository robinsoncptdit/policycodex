// @ts-check
import { defineConfig } from 'astro/config';

export default defineConfig({
  // Site is required for canonical URLs at build time. Replace with the
  // diocese's deploy URL when PUBLISH-07 wires the production subdomain.
  site: 'https://handbook.example.org',
});
