"""Unit tests for the foundational typed-table editor formsets (APP-25)."""
from core.forms import (
    ClassificationForm,
    ClassificationFormSet,
    RetentionRowForm,
    RetentionRowFormSet,
)


def _mgmt(prefix, total, initial):
    return {
        f"{prefix}-TOTAL_FORMS": str(total),
        f"{prefix}-INITIAL_FORMS": str(initial),
        f"{prefix}-MIN_NUM_FORMS": "0",
        f"{prefix}-MAX_NUM_FORMS": "1000",
    }


def test_classification_form_requires_id_and_name():
    form = ClassificationForm(data={"id": "", "name": ""})
    assert not form.is_valid()
    assert "id" in form.errors
    assert "name" in form.errors


def test_retention_row_requires_group_type_retention():
    form = RetentionRowForm(data={"group": "", "type": "", "retention": ""})
    assert not form.is_valid()
    assert "group" in form.errors
    assert "type" in form.errors
    assert "retention" in form.errors


def test_retention_row_optional_fields_not_required():
    form = RetentionRowForm(data={"group": "G", "type": "T", "retention": "3 years"})
    assert form.is_valid(), form.errors
    assert form.cleaned_data["sub_group"] == ""
    assert form.cleaned_data["medium"] == ""
    assert form.cleaned_data["retained_at"] == ""


def test_classification_formset_extra_blank_row_is_ignored():
    data = _mgmt("cls", total=2, initial=1)
    data.update({
        "cls-0-id": "administrative", "cls-0-name": "Administrative",
        "cls-1-id": "", "cls-1-name": "",  # blank extra -> ignored
    })
    fs = ClassificationFormSet(data, prefix="cls")
    assert fs.is_valid(), fs.errors
    filled = [f.cleaned_data for f in fs if f.cleaned_data and not f.cleaned_data.get("DELETE")]
    assert filled == [{"id": "administrative", "name": "Administrative", "DELETE": False}]


def test_classification_formset_marks_delete():
    data = _mgmt("cls", total=2, initial=2)
    data.update({
        "cls-0-id": "administrative", "cls-0-name": "Administrative",
        "cls-1-id": "legal", "cls-1-name": "Legal", "cls-1-DELETE": "on",
    })
    fs = ClassificationFormSet(data, prefix="cls")
    assert fs.is_valid(), fs.errors
    kept = [f.cleaned_data["id"] for f in fs
            if f.cleaned_data and not f.cleaned_data.get("DELETE")]
    assert kept == ["administrative"]
