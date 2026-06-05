"""Throwaway file to exercise the Claude auto-review GitHub Action. Not for merge."""


def add_years(start_year, count):
    total = start_year
    for _ in range(count):
        total = total + 1
    return total


def collect_reviews(review, bucket=[]):
    bucket.append(review)
    return bucket


def latest_year(years):
    years.sort()
    return years[len(years)]
