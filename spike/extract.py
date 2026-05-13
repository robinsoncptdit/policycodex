"""
PolicyWonk Inventory Pass Spike

Extracts structured metadata from Catholic diocese policy documents
using Claude. See ../PolicyWonk-Spike-Plan.md for context.

Usage:
    python extract.py <input_dir> <output_dir>

Input formats supported: .txt, .md, .pdf, .docx
"""
import csv
import json
import os
import sys
from pathlib import Path

import yaml
from anthropic import Anthropic
from dotenv import load_dotenv

load_dotenv()

# Switch to "claude-opus-4-6" if Sonnet acceptance is marginal.
MODEL = os.getenv("POLICYWONK_MODEL", "claude-sonnet-4-6")

# Seed taxonomy for the install-zero diocese (Pensacola-Tallahassee).
# Built from the diocese's Document Retention Policy (rev. Aug, 2022).
# When the Week-3 bundle scaffolding lands this file moves to
# policies/document-retention/data.yaml; the injection logic is the same.
TAXONOMY_PATH = Path(__file__).resolve().parent.parent / "ai" / "taxonomies" / "pt_classification.yaml"

def _load_taxonomy(path: Path = TAXONOMY_PATH) -> dict:
    """Read the PT taxonomy YAML once at import time."""
    with path.open(encoding="utf-8") as fh:
        return yaml.safe_load(fh)


# Acceptable sample-size band for the rendered prompt section. Catches
# silent drift if the YAML structure changes (e.g., a group is split or
# merged) and the rendered sample falls outside the expected shape.
_MIN_SAMPLE_ROWS = 20
_MAX_SAMPLE_ROWS = 50


def _build_taxonomy_section(taxonomy: dict) -> str:
    """Render the taxonomy into a prompt section.

    Includes all 8 top-level classifications and one example retention
    row per (group, sub_group) pair, in YAML order. The full schedule
    has ~240 rows; pulling one per pair keeps the prompt budget bounded
    while giving the model coverage of every department.
    """
    lines = []
    lines.append("## Diocese taxonomy reference (Diocese of Pensacola-Tallahassee)")
    lines.append("")
    lines.append("Top-level data classifications (Section 3.0 of the diocesan retention policy):")
    for entry in taxonomy.get("classifications", []):
        lines.append(f"- {entry['id']}: {entry['name']}")
    lines.append("")
    lines.append("Retention schedule (one example per group/sub-group; the full schedule has ~240 rows):")
    seen_pairs: set[tuple[str, str | None]] = set()
    sampled = 0
    for row in taxonomy.get("retention_schedule", []):
        pair = (row["group"], row.get("sub_group"))
        if pair in seen_pairs:
            continue
        seen_pairs.add(pair)
        sampled += 1
        group_label = row["group"]
        if row.get("sub_group"):
            group_label = f"{group_label} / {row['sub_group']}"
        lines.append(f"- {group_label}: {row['type']} -> {row['retention']}")
    if not (_MIN_SAMPLE_ROWS <= sampled <= _MAX_SAMPLE_ROWS):
        raise RuntimeError(
            f"Retention sample size {sampled} out of expected range "
            f"[{_MIN_SAMPLE_ROWS}, {_MAX_SAMPLE_ROWS}]; "
            f"the YAML structure may have drifted."
        )
    lines.append("")
    return "\n".join(lines)


TAXONOMY = _load_taxonomy()
TAXONOMY_SECTION = _build_taxonomy_section(TAXONOMY)


EXTRACTION_PROMPT = """\
You are a policy librarian for a Catholic diocese. You read a single
governing document (policy, procedure, or by-law) and extract structured
metadata. Be conservative. If a field is not stated or strongly implied
in the text, leave it null and lower your confidence.

""" + TAXONOMY_SECTION + """

When extracting `category` and `suggested_chapter_section_item`, PREFER
values that align with the diocese taxonomy above. Map your category
choice to one of the schema-defined category values (Finance, HR, IT,
Safe Environment, Schools, Worship, Parish Operations, Stewardship,
By-Laws, Communications, Risk, Other) but choose the one whose meaning
most closely matches the relevant classification or retention group.
For `suggested_chapter_section_item`, use a chapter.section.item address
(e.g., 5.2.8) where the chapter aligns with the classification axis or
retention group most relevant to the policy. If the policy doesn't
cleanly fit any provided category or group, use your best judgment and
note this in `notes`.

Output strictly as JSON, matching this schema:

{
  "title": "<the policy's title as best you can identify>",
  "summary": "<one sentence describing what this policy governs>",
  "category": "<one of: Finance, HR, IT, Safe Environment, Schools, Worship, Parish Operations, Stewardship, By-Laws, Communications, Risk, Other>",
  "category_confidence": "<low | medium | high>",
  "owner_role": "<best guess at the diocesan role responsible: CFO, HR Director, IT Director, Vicar General, Chancellor, Superintendent of Schools, Director of Safe Environment, etc.>",
  "owner_role_confidence": "<low | medium | high>",
  "effective_date": "<ISO date if stated, else null>",
  "effective_date_confidence": "<low | medium | high>",
  "last_review_date": "<ISO date if stated, else null>",
  "last_review_date_confidence": "<low | medium | high>",
  "next_review_date": "<ISO date if stated, or computed from effective date plus implied cadence, else null>",
  "next_review_date_confidence": "<low | medium | high>",
  "retention_period_years": "<integer years if stated or inferable from records-management norms, else null>",
  "retention_period_confidence": "<low | medium | high>",
  "suggested_chapter_section_item": "<chapter.section.item address using LA-Archdiocese-style numbering, e.g., 5.2.8>",
  "address_confidence": "<low | medium | high>",
  "version_stamp": "1.0",
  "notes": "<anything ambiguous, missing, or concerning that a human reviewer should know>"
}

Document text follows. Output only the JSON object.
---
"""


def extract_text(path: Path) -> str:
    """Read file content from supported formats."""
    suffix = path.suffix.lower()
    if suffix in (".txt", ".md"):
        return path.read_text(encoding="utf-8", errors="replace")
    if suffix == ".pdf":
        try:
            import pypdf
        except ImportError:
            print(f"  skip {path.name}: pip install pypdf for PDF support", file=sys.stderr)
            return ""
        reader = pypdf.PdfReader(str(path))
        return "\n".join(page.extract_text() or "" for page in reader.pages)
    if suffix == ".docx":
        try:
            import docx
        except ImportError:
            print(f"  skip {path.name}: pip install python-docx for DOCX support", file=sys.stderr)
            return ""
        document = docx.Document(str(path))
        return "\n".join(p.text for p in document.paragraphs)
    return ""


def extract_metadata(client: Anthropic, document_text: str) -> dict:
    """Run the extraction prompt against a single document."""
    response = client.messages.create(
        model=MODEL,
        max_tokens=2048,
        messages=[{
            "role": "user",
            "content": EXTRACTION_PROMPT + document_text[:50000],
        }],
    )
    raw = response.content[0].text.strip()
    # strip code fences if Claude wrapped the JSON
    if raw.startswith("```"):
        raw = raw.split("```", 2)[1]
        if raw.startswith("json"):
            raw = raw[4:].strip()
        raw = raw.rstrip("`").strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        return {"_error": f"JSON decode failed: {exc}", "_raw": raw}


def write_combined_csv(results: list, path: Path) -> None:
    """Write all extractions to a single CSV for human scoring."""
    fields = [
        "_source_file",
        "title",
        "category",
        "category_confidence",
        "owner_role",
        "owner_role_confidence",
        "effective_date",
        "last_review_date",
        "next_review_date",
        "retention_period_years",
        "suggested_chapter_section_item",
        "address_confidence",
        "summary",
        "notes",
    ]
    # add scoring columns the reviewer will fill in
    score_columns = [
        "score_category",
        "score_owner_role",
        "score_effective_date",
        "score_last_review_date",
        "score_next_review_date",
        "score_retention",
        "score_address",
        "score_title",
        "reviewer_notes",
    ]
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields + score_columns, extrasaction="ignore")
        writer.writeheader()
        for record in results:
            writer.writerow(record)


def main() -> None:
    if len(sys.argv) != 3:
        print("Usage: python extract.py <input_dir> <output_dir>", file=sys.stderr)
        sys.exit(1)

    input_dir = Path(sys.argv[1])
    output_dir = Path(sys.argv[2])
    output_dir.mkdir(parents=True, exist_ok=True)

    if not input_dir.is_dir():
        print(f"Input directory not found: {input_dir}", file=sys.stderr)
        sys.exit(1)

    client = Anthropic()
    files = sorted([p for p in input_dir.iterdir() if p.is_file()])

    if not files:
        print(f"No files in {input_dir}. Drop 15-20 policy files there and re-run.", file=sys.stderr)
        sys.exit(1)

    print(f"Processing {len(files)} files with {MODEL}...")
    results = []
    for path in files:
        print(f"  {path.name}")
        document_text = extract_text(path)
        if not document_text.strip():
            print(f"    no extractable text, skipping")
            continue
        metadata = extract_metadata(client, document_text)
        metadata["_source_file"] = path.name
        results.append(metadata)
        per_file = output_dir / f"{path.stem}.json"
        per_file.write_text(json.dumps(metadata, indent=2), encoding="utf-8")

    csv_path = output_dir / "results.csv"
    write_combined_csv(results, csv_path)
    print(f"\nDone. {len(results)} extractions in {output_dir}")
    print(f"Open {csv_path} and score using the rubric in PolicyWonk-Spike-Plan.md.")


if __name__ == "__main__":
    main()
