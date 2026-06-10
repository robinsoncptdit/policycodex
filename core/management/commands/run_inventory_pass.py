"""Run the AI inventory pass over a local folder of policy files (AI-10 + AI-17).

Wires the incremental ingest pipeline to the orchestrator: walk the source
folder, diff against the persisted manifest (added vs changed vs unchanged
vs removed), load the diocese's live foundational taxonomy from the working
copy, and hand everything to ai.inventory.run_inventory_pass, which writes
draft markdown + audit sidecars for the NEW sources, surfaces CHANGED
sources in a dedicated bucket (existing drafts preserved), and opens one
bulk draft PR. The persisted manifest is written only after the orchestrator
returns without raising (crash-safe per ingest.incremental).

Precondition: the working copy must be synced (run `manage.py
pull_working_copy` first) and must already contain the document-retention
foundational bundle (scaffolded during onboarding). The taxonomy is required
so extraction has retention/address grounding.
"""
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from ai.claude_provider import ClaudeProvider
from ai.inventory import REQUIRED_CAPABILITIES, run_inventory_pass
from ai.taxonomy_loader import load_foundational_taxonomy
from app.git_provider.github_provider import GitHubProvider
from app.working_copy.config import load_working_copy_config
from ingest.incremental import plan_incremental_run, save_manifest


class Command(BaseCommand):
    help = "Run the AI inventory pass over a local folder; open one bulk draft PR."

    def add_arguments(self, parser):
        parser.add_argument("source_folder", help="Folder of policy files to ingest.")
        parser.add_argument("--author-name", default="PolicyCodex")
        parser.add_argument("--author-email", default="bot@policycodex.local")
        parser.add_argument("--source-label", default="local-folder")
        parser.add_argument(
            "--manifest-path",
            default=None,
            help=(
                "Path to the persisted ingest manifest (AI-17). Default: "
                "<working_dir>/.policycodex/ingest-manifest.json. Override "
                "when running against multiple source folders so each folder "
                "keeps its own incremental state."
            ),
        )

    def handle(self, *args, **options):
        config = load_working_copy_config()
        working_dir = Path(config.working_dir)
        policies_dir = working_dir / "policies"

        taxonomy = load_foundational_taxonomy(policies_dir, REQUIRED_CAPABILITIES)
        if taxonomy is None:
            raise CommandError(
                f"No foundational retention bundle found under {policies_dir}. "
                "Complete onboarding so the document-retention bundle exists, "
                "then re-run; extraction needs the retention schedule for grounding."
            )

        source = Path(options["source_folder"])
        manifest_path = (
            Path(options["manifest_path"])
            if options["manifest_path"]
            else working_dir / ".policycodex" / "ingest-manifest.json"
        )
        manifest_path.parent.mkdir(parents=True, exist_ok=True)

        diff = plan_incremental_run(
            source, manifest_path, source_label=options["source_label"]
        )

        result = run_inventory_pass(
            manifest=diff.added,
            changed_entries=diff.changed,
            working_dir=working_dir,
            provider=GitHubProvider(),
            llm_provider=ClaudeProvider(),
            taxonomy=taxonomy,
            author_name=options["author_name"],
            author_email=options["author_email"],
            base_branch=config.branch,
        )
        self._report(result, removed_count=len(diff.removed))
        # AI-17: persist the manifest ONLY after run_inventory_pass returns
        # without raising. If the orchestrator raises (push failure, LLM down,
        # etc.) the prior manifest stays intact and the next run re-diffs
        # against it -- no source file is silently marked already-seen.
        save_manifest(diff.current, manifest_path)

    def _report(self, result, removed_count=0):
        self.stdout.write(self.style.SUCCESS(
            f"wrote {len(result.written)} drafts; "
            f"skipped {len(result.skipped_existing)} existing, "
            f"{len(result.skipped_changed)} changed (existing drafts preserved), "
            f"{len(result.skipped_empty)} empty, "
            f"{len(result.skipped_unsupported)} unsupported; "
            f"{len(result.errors)} extraction errors"
        ))
        if result.skipped_changed:
            self.stdout.write(self.style.WARNING(
                "  source files changed since last inventory (review manually):"
            ))
            for slug in result.skipped_changed:
                self.stdout.write(self.style.WARNING(f"    - {slug}"))
        if removed_count:
            self.stdout.write(
                f"{removed_count} source files removed since last inventory "
                "(drafts kept)"
            )
        if result.errors:
            for slug, msg in result.errors.items():
                self.stdout.write(self.style.WARNING(f"  error {slug}: {msg}"))
        if result.pr:
            self.stdout.write(self.style.SUCCESS(f"opened PR: {result.pr.get('url')}"))
        else:
            self.stdout.write("no PR opened (nothing new to draft)")
