"""Run the AI inventory pass over a local folder of policy files (AI-10).

Wires the ingest pipeline to the orchestrator: walk the source folder, build a
manifest, load the diocese's live foundational taxonomy from the working copy,
and hand everything to ai.inventory.run_inventory_pass, which writes draft
markdown + audit sidecars and opens one bulk draft PR.

Precondition: the working copy must be synced (run `manage.py
pull_working_copy` first) and must already contain the document-retention
foundational bundle (scaffolded during onboarding). The taxonomy is required so
extraction has retention/address grounding.
"""
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from ai.claude_provider import ClaudeProvider
from ai.inventory import REQUIRED_CAPABILITIES, run_inventory_pass
from ai.taxonomy_loader import load_foundational_taxonomy
from app.git_provider.github_provider import GitHubProvider
from app.working_copy.config import load_working_copy_config
from ingest.local_folder import LocalFolderConnector
from ingest.manifest import build_manifest


class Command(BaseCommand):
    help = "Run the AI inventory pass over a local folder; open one bulk draft PR."

    def add_arguments(self, parser):
        parser.add_argument("source_folder", help="Folder of policy files to ingest.")
        parser.add_argument("--author-name", default="PolicyCodex")
        parser.add_argument("--author-email", default="bot@policycodex.local")
        parser.add_argument("--source-label", default="local-folder")

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
        paths = list(LocalFolderConnector(source).walk())
        manifest = build_manifest(paths, options["source_label"])

        result = run_inventory_pass(
            manifest=manifest,
            working_dir=working_dir,
            provider=GitHubProvider(),
            llm_provider=ClaudeProvider(),
            taxonomy=taxonomy,
            author_name=options["author_name"],
            author_email=options["author_email"],
            base_branch=config.branch,
        )
        self._report(result)

    def _report(self, result):
        self.stdout.write(self.style.SUCCESS(
            f"wrote {len(result.written)} drafts; "
            f"skipped {len(result.skipped_existing)} existing, "
            f"{len(result.skipped_empty)} empty, "
            f"{len(result.skipped_unsupported)} unsupported; "
            f"{len(result.errors)} extraction errors"
        ))
        if result.errors:
            for slug, msg in result.errors.items():
                self.stdout.write(self.style.WARNING(f"  error {slug}: {msg}"))
        if result.pr:
            self.stdout.write(self.style.SUCCESS(f"opened PR: {result.pr.get('url')}"))
        else:
            self.stdout.write("no PR opened (nothing new to draft)")
