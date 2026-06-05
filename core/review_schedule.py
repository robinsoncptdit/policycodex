"""Helpers for computing a policy's review-schedule status from its metadata.

A published policy carries a `last_review` date and a review interval (in years).
These helpers derive the next due date and whether that date has passed.
"""

from datetime import date


def next_review_date(last_review: date, interval_years: int) -> date:
    """Return the date the policy is next due for review."""
    return last_review.replace(year=last_review.year + interval_years)


def is_review_overdue(last_review: date, interval_years: int, today: date) -> bool:
    """Return True when the next scheduled review date has already passed."""
    due = next_review_date(last_review, interval_years)
    return due > today
