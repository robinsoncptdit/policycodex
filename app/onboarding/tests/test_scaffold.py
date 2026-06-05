"""Scaffolder writes a valid foundational bundle (APP-15)."""
import yaml

from app.onboarding.scaffold import scaffold_retention_bundle
from ingest.policy_reader import BundleAwarePolicyReader

DATA_YAML = (
    "classifications:\n"
    "- id: administrative\n"
    "  name: Administrative\n"
    "- id: financial\n"
    "  name: Financial\n"
    "retention_schedule:\n"
    "- group: Administrative Records\n"
    "  type: General correspondence\n"
    "  retention: 3 years\n"
)


def test_scaffold_writes_readable_foundational_bundle(tmp_path):
    policies_dir = tmp_path / "policies"
    policies_dir.mkdir()
    source_pdf = tmp_path / "src.pdf"
    source_pdf.write_bytes(b"%PDF-1.4 fake")

    bundle_dir = scaffold_retention_bundle(
        policies_dir,
        title="Document Retention Policy",
        owner="CFO",
        narrative="# Document Retention Policy\n\nBootstrapped.\n",
        data_yaml_text=DATA_YAML,
        source_pdf=source_pdf,
    )

    assert bundle_dir == policies_dir / "document-retention"
    assert (bundle_dir / "policy.md").is_file()
    assert (bundle_dir / "data.yaml").is_file()
    assert (bundle_dir / "source.pdf").read_bytes() == b"%PDF-1.4 fake"

    policies = list(BundleAwarePolicyReader(policies_dir).read())
    assert len(policies) == 1
    policy = policies[0]
    assert policy.slug == "document-retention"
    assert policy.kind == "bundle"
    assert policy.foundational is True
    assert policy.provides == ("classifications", "retention-schedule")
    assert policy.frontmatter["title"] == "Document Retention Policy"

    data = yaml.safe_load((bundle_dir / "data.yaml").read_text())
    assert [c["id"] for c in data["classifications"]] == ["administrative", "financial"]


def test_scaffold_without_source_pdf_omits_it(tmp_path):
    policies_dir = tmp_path / "policies"
    policies_dir.mkdir()
    bundle_dir = scaffold_retention_bundle(
        policies_dir, title="T", owner="CFO",
        narrative="# T\n", data_yaml_text=DATA_YAML, source_pdf=None,
    )
    assert not (bundle_dir / "source.pdf").exists()
    assert list(BundleAwarePolicyReader(policies_dir).read())[0].foundational is True
