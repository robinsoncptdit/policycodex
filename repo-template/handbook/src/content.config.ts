import { defineCollection, z } from 'astro:content';
import { glob } from 'astro/loaders';

const policies = defineCollection({
  // Glob picks up BOTH flat `<slug>.md` and bundle `<slug>/policy.md` files.
  // Astro derives the slug from the path; for bundles, the slug is the
  // parent directory name with `/policy` appended.
  loader: glob({ pattern: ['*.md', '*/policy.md'], base: './src/content/policies' }),
  schema: z.object({
    title: z.string(),
    owner: z.string().optional(),
    foundational: z.boolean().default(false),
    provides: z.array(z.string()).default([]),
    effective_date: z.coerce.date().optional(),
    last_review: z.coerce.date().optional(),
    retention_period: z.string().optional(),
  }).refine(
    (data) => !data.foundational || data.provides.length > 0,
    {
      message: 'foundational policies must declare a non-empty provides: [...] list',
      path: ['provides'],
    }
  ),
});

export const collections = { policies };
