# PolicyWonk Static-Site Generator Evaluation (PUBLISH-01)

**Date:** 2026-05-08
**Author:** Explore subagent (Claude, Friday-night Phase 2 dispatch)
**Status:** Resolved 2026-05-11. Chuck overrode the Hugo recommendation and picked **Astro**. Driver: parish web teams forking the handbook theme will find Astro's component model more approachable than Hugo's Go templates. Build-speed and GitHub Actions ergonomics are acceptable losses given the handbook ships through CI either way. The Hugo analysis below is preserved as-written for the record; treat it as the dissenting opinion, not the active plan.

## Evaluation Criteria

Per v0.1 spec P0.5 and tickets PUBLISH-01..08:

1. Markdown + YAML front matter ingestion
2. Chapter.section.item URL scheme (e.g., `/5/2/8/`) with stable per-policy URLs
3. RSS feed support
4. Changelog page from `git log`
5. GitHub Actions ergonomics
6. Theme creation modeled on the LA archdiocese handbook
7. Build speed for a 200-policy diocese
8. PUBLISH-08 vector-friendly chunk export (v0.2 RAG)

## Comparative Table

| Criterion | Astro | Hugo | Eleventy |
|-----------|-------|------|----------|
| Markdown + YAML | ★★★★★ | ★★★★★ | ★★★★★ |
| Chapter.section.item routing | ★★★★★ | ★★★★☆ | ★★★★★ |
| RSS feed | ★★★★★ | ★★★★★ | ★★★☆☆ |
| Git log changelog | ★★★★☆ | ★★★☆☆ | ★★★★☆ |
| GitHub Actions ergonomics | ★★☆☆☆ | ★★★★★ | ★★★☆☆ |
| Theme (LA-style) | ★★★★★ | ★★★☆☆ | ★★★★☆ |
| Build speed (200 policies) | ★★★☆☆ | ★★★★★ | ★★★★☆ |
| Chunk export (v0.2 RAG) | ★★★★★ | ★★☆☆☆ | ★★★★★ |

## Recommendation: Hugo

Rationale (subagent's words, condensed):

1. **Critical path alignment.** Hugo's single-binary simplicity and sub-second builds let the PUBLISH-01 spike validate in hours, not days.
2. **GitHub Actions feedback loop.** ~5 seconds total CI time (download binary, build, deploy) versus 25–50s overhead for Astro/Eleventy.
3. **Content model fit.** Markdown + YAML front matter is Hugo's native idiom; sections-as-directories maps directly to chapter-section-item.
4. **RSS and changelog are solved problems.** Hugo's built-in RSS template plus a `git log --json | jq` post-build step handles both.
5. **Theme portability.** LA archdiocese handbook theming is CSS + HTML; Hugo's templates plus a Git submodule covers it.
6. **PUBLISH-08 fallback is acceptable.** A standalone Python post-build script reads Hugo's generated JSON and emits vector chunks. Not elegant, but unblocked.

## Trade-offs

- Hugo's Go templates are less flexible than Astro's components for future dynamic features (e.g., v0.2 Q&A chatbot). v0.1's charter is static handbook delivery, so this trade-off is acceptable.
- If v0.2 pivots to heavily dynamic content, a Hugo → Astro migration is feasible (markdown and YAML are portable).

## PUBLISH-08 Implications

For all three candidates, the recommended chunk-export pattern is the same: a standalone post-build script reading the generator's output JSON, chunking by section, emitting vectors with metadata to a `vectors/` directory. v0.2 RAG ingest reads from there. No re-extraction of source markdown needed.

## Open follow-ups for Chuck

- Sign off on Hugo (OQ-09)
- Defer the Hugo theme work to PUBLISH-03 (Week 3)
- PUBLISH-08 chunk-export script remains a Week 5 placeholder
