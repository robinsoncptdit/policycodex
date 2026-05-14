"""Sync the local working copy of the diocese's policy repo.

Run on cadence via cron (~5 minute interval) to keep the app's read-side
consistent with the diocese's GitHub repo. Idempotent: clones on first
run, pulls on subsequent runs. Safe to invoke from APP-21's startup
self-check.
"""
from django.core.management.base import BaseCommand

from app.git_provider.github_provider import GitHubProvider
from app.working_copy.config import load_working_copy_config
from app.working_copy.manager import WorkingCopyManager


class Command(BaseCommand):
    help = "Clone (first run) or pull (subsequent runs) the diocese's policy repo."

    def handle(self, *args, **options):
        config = load_working_copy_config()
        provider = GitHubProvider()
        manager = WorkingCopyManager(config, provider)
        working_dir = manager.sync()
        self.stdout.write(self.style.SUCCESS(f"working copy synced at {working_dir}"))
