"""Django forms for the core app."""
from django import forms


class PolicyEditForm(forms.Form):
    """Edit form for a single non-foundational policy (APP-07).

    Editable surface in v0.1: title (frontmatter), body (markdown), and an
    optional one-line summary that becomes the commit message + PR title
    suffix.

    Other frontmatter keys (owner, effective_date, retention, ...) are
    preserved round-trip by the view but NOT exposed here. The typed-table
    UI (future ticket) will expose them.
    """

    title = forms.CharField(
        max_length=200,
        required=True,
        widget=forms.TextInput(attrs={"autocomplete": "off"}),
    )
    body = forms.CharField(
        required=True,
        widget=forms.Textarea(attrs={"rows": 20, "cols": 80}),
    )
    summary = forms.CharField(
        max_length=200,
        required=False,
        help_text="Optional one-line description of your change. Becomes the commit message.",
        widget=forms.TextInput(attrs={"autocomplete": "off"}),
    )


class ClassificationForm(forms.Form):
    """One classification row (id + display name) in the typed-table editor (APP-25)."""
    id = forms.SlugField(
        label="id",
        help_text="Stable lowercase slug; other policies reference this.",
        widget=forms.TextInput(attrs={"autocomplete": "off"}),
    )
    name = forms.CharField(
        max_length=200,
        label="name",
        widget=forms.TextInput(attrs={"autocomplete": "off"}),
    )
    deprecated = forms.BooleanField(
        label="deprecated",
        required=False,
        help_text="Soft-delete: hides for new uses, keeps the id valid for existing references.",
    )


class RetentionRowForm(forms.Form):
    """One retention-schedule row. group/type/retention required; rest optional."""
    group = forms.CharField(max_length=300, widget=forms.TextInput(attrs={"autocomplete": "off"}))
    sub_group = forms.CharField(max_length=300, required=False, widget=forms.TextInput(attrs={"autocomplete": "off"}))
    type = forms.CharField(max_length=500, widget=forms.TextInput(attrs={"autocomplete": "off"}))
    retention = forms.CharField(max_length=200, widget=forms.TextInput(attrs={"autocomplete": "off"}))
    medium = forms.CharField(max_length=120, required=False, widget=forms.TextInput(attrs={"autocomplete": "off"}))
    retained_at = forms.CharField(max_length=200, required=False, widget=forms.TextInput(attrs={"autocomplete": "off"}))


class FoundationalEditMetaForm(forms.Form):
    """The commit-message summary for a foundational edit."""
    summary = forms.CharField(
        max_length=200,
        required=False,
        help_text="Optional one-line description of your change. Becomes the commit message.",
        widget=forms.TextInput(attrs={"autocomplete": "off"}),
    )


ClassificationFormSet = forms.formset_factory(
    ClassificationForm, can_delete=True, extra=1
)
RetentionRowFormSet = forms.formset_factory(
    RetentionRowForm, can_delete=True, extra=1
)
