from pathlib import Path
from types import SimpleNamespace
from ingest.policy_reader import LogicalPolicy
from core.policy_writer import _render_policy_md
from core.git_identity import get_git_author
from core.services import propose_policy_edit
from core.forms import ClassificationFormSet, RetentionRowFormSet
from core.services import build_foundational_bundle, propose_foundational_edit
from ai.retention_extract import build_data_yaml


def _user():
    return SimpleNamespace(username="editor", is_authenticated=True,
                           get_full_name=lambda: "Pat Editor", email="editor@example.com")


def test_propose_policy_edit_writes_file_and_calls_propose(tmp_path):
    pdir = tmp_path / "policies"; pdir.mkdir()
    pf = pdir / "onboarding.md"
    pf.write_text("---\ntitle: Old\nowner: HR\n---\nOld body.\n", encoding="utf-8")
    policy = LogicalPolicy(slug="onboarding", kind="flat", policy_path=pf, data_path=None,
                           frontmatter={"title": "Old", "owner": "HR"}, body="Old body.\n",
                           foundational=False, provides=())
    config = SimpleNamespace(working_dir=tmp_path, branch="main")
    calls = {}
    def fake_propose(**kw):
        calls.update(kw); return {"pr_number": 9, "url": "u", "state": "open"}
    pr = propose_policy_edit(policy, "onboarding", user=_user(),
                             title="New Title", body="New body.\n", summary="Tighten",
                             config=config, provider=object(), branch_name="policycodex/edit-onboarding-deadbeef",
                             render_md=_render_policy_md, git_author_fn=get_git_author, propose_fn=fake_propose)
    assert pr["pr_number"] == 9
    written = pf.read_text(encoding="utf-8")
    assert "title: New Title" in written and "owner: HR" in written and "New body." in written
    assert calls["files"] == [pf]
    assert calls["commit_message"] == "Tighten"
    assert calls["default_branch"] == "main"
    assert calls["author_name"] == "Pat Editor" and calls["author_email"] == "editor@example.com"
    assert "onboarding" in calls["pr_title"] and "Tighten" in calls["pr_title"]
    assert "Opened by PolicyCodex on behalf of editor" in calls["pr_body"]


def test_propose_policy_edit_default_commit_message_when_summary_blank(tmp_path):
    pf = tmp_path / "p.md"; pf.write_text("---\ntitle: T\n---\nb\n", encoding="utf-8")
    policy = LogicalPolicy(slug="onboarding", kind="flat", policy_path=pf, data_path=None,
                           frontmatter={"title": "T"}, body="b\n", foundational=False, provides=())
    config = SimpleNamespace(working_dir=tmp_path, branch="main")
    got = {}
    propose_policy_edit(policy, "onboarding", user=_user(), title="T2", body="b2\n", summary="",
                        config=config, provider=object(), branch_name="b",
                        render_md=_render_policy_md, git_author_fn=get_git_author,
                        propose_fn=lambda **kw: got.update(kw) or {})
    assert got["commit_message"] == "Update onboarding"


def _bound_formsets(cls_rows, ret_rows, *, cls_initial, ret_initial):
    # TOTAL_FORMS == len(rows): every row (incl. new-extra rows) is encoded
    # explicitly here, so there is no trailing blank form to account for.
    def mgmt(prefix, rows, initial):
        d = {f"{prefix}-TOTAL_FORMS": str(len(rows)), f"{prefix}-INITIAL_FORMS": str(initial),
             f"{prefix}-MIN_NUM_FORMS": "0", f"{prefix}-MAX_NUM_FORMS": "1000"}
        for i, r in enumerate(rows):
            for k, v in r.items():
                d[f"{prefix}-{i}-{k}"] = v
        return d
    data = {**mgmt("cls", cls_rows, cls_initial), **mgmt("ret", ret_rows, ret_initial)}
    c = ClassificationFormSet(data, prefix="cls"); r = RetentionRowFormSet(data, prefix="ret")
    assert c.is_valid() and r.is_valid()
    return c, r


def test_build_foundational_bundle_soft_deletes_existing_drops_new():
    c, r = _bound_formsets(
        cls_rows=[{"id": "administrative", "name": "Admin"},
                  {"id": "financial", "name": "Financial", "DELETE": "on"},   # existing -> tombstone
                  {"id": "legal", "name": "Legal", "DELETE": "on"}],          # new extra -> dropped
        ret_rows=[{"group": "G", "type": "T", "retention": "3 years"}],
        cls_initial=2, ret_initial=1)
    bundle = build_foundational_bundle(c, r)
    assert bundle["classifications"] == [
        {"id": "administrative", "name": "Admin"},
        {"id": "financial", "name": "Financial", "deprecated": True},
    ]
    assert bundle["retention_schedule"][0]["retention"] == "3 years"


def test_propose_foundational_edit_writes_yaml_and_calls_propose(tmp_path):
    import yaml as _yaml
    dp = tmp_path / "data.yaml"; dp.write_text("classifications: []\n", encoding="utf-8")
    policy = LogicalPolicy(slug="document-retention", kind="bundle",
                           policy_path=tmp_path / "policy.md", data_path=dp,
                           frontmatter={}, body="", foundational=True, provides=("classifications",))
    user = SimpleNamespace(username="editor", is_authenticated=True,
                           get_full_name=lambda: "Pat Editor", email="editor@example.com")
    config = SimpleNamespace(working_dir=tmp_path, branch="main")
    bundle = {"classifications": [{"id": "a", "name": "A"}],
              "retention_schedule": [{"group": "G", "type": "T", "retention": "3 years"}]}
    got = {}
    pr = propose_foundational_edit(policy, "document-retention", bundle=bundle, summary="msg",
            user=user, config=config, provider=object(), branch_name="policycodex/edit-document-retention-abcd",
            build_yaml_fn=build_data_yaml, git_author_fn=get_git_author,
            propose_fn=lambda **kw: got.update(kw) or {"pr_number": 31, "url": "u", "state": "open"})
    assert pr["pr_number"] == 31
    written = _yaml.safe_load(dp.read_text())
    assert written["classifications"][0]["id"] == "a"
    assert got["files"] == [dp] and got["default_branch"] == "main"
    assert "document-retention" in got["pr_title"]
    assert "Opened by PolicyCodex on behalf of editor" in got["pr_body"]
    assert "document-retention" in got["pr_body"]
