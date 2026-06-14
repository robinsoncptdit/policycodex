from pathlib import Path
from types import SimpleNamespace
from ingest.policy_reader import LogicalPolicy
from core.policy_writer import _render_policy_md
from core.git_identity import get_git_author
from core.services import propose_policy_edit


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
