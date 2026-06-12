"""DISC-11: persistent state for one onboarding inventory pass."""
from django.db import models


class InventoryRun(models.Model):
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=16)  # pending|running|completed|failed|interrupted
    total = models.IntegerField(default=0)
    completed = models.IntegerField(default=0)
    failed = models.IntegerField(default=0)
    pr_url = models.URLField(blank=True)
    pr_error = models.TextField(blank=True)
    # Absolute path to the directory where uploaded files were staged.
    # Recorded so retry can re-spawn the runner against the original payload.
    stage_dir = models.CharField(max_length=512, blank=True)


class InventoryItem(models.Model):
    run = models.ForeignKey(InventoryRun, related_name="items", on_delete=models.CASCADE)
    source_filename = models.CharField(max_length=512)
    slug = models.CharField(max_length=128, blank=True)
    title = models.CharField(max_length=256, blank=True)
    classification = models.CharField(max_length=64, blank=True)
    confidence = models.FloatField(null=True, blank=True)
    status = models.CharField(max_length=16, default="pending")  # pending|extracting|done|failed
    error_message = models.TextField(blank=True)
