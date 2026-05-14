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
