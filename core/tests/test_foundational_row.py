"""APP-28c: the /htmx/foundational/<slug>/row/ endpoint returns one fresh
typed-table row plus an out-of-band bump of that formset's TOTAL_FORMS."""
import pytest
from django.urls import reverse

pytestmark = pytest.mark.django_db


def test_foundational_row_classification_returns_indexed_tr(client, django_user_model):
    user = django_user_model.objects.create_user("u", password="p")
    client.force_login(user)
    url = reverse("htmx:foundational_row", kwargs={"slug": "document-retention"})
    resp = client.post(url, {"formset": "cls", "index": "3"})
    assert resp.status_code == 200
    body = resp.content.decode()
    assert 'name="cls-3-id"' in body
    assert 'name="cls-3-name"' in body
    assert 'name="cls-TOTAL_FORMS"' in body
    # The OOB swap only lands if this id matches Django's management-form id
    # char-for-char; a regressed id no-ops silently and breaks formset submit.
    assert 'id="id_cls-TOTAL_FORMS"' in body
    assert 'hx-swap-oob="true"' in body
    assert 'value="4"' in body


def test_foundational_row_retention_returns_indexed_tr(client, django_user_model):
    user = django_user_model.objects.create_user("u", password="p")
    client.force_login(user)
    url = reverse("htmx:foundational_row", kwargs={"slug": "document-retention"})
    resp = client.post(url, {"formset": "ret", "index": "0"})
    assert resp.status_code == 200
    body = resp.content.decode()
    assert 'name="ret-0-group"' in body
    assert 'name="ret-0-sub_group"' in body
    assert 'name="ret-0-type"' in body
    assert 'name="ret-0-retention"' in body
    assert 'name="ret-0-medium"' in body
    assert 'name="ret-0-retained_at"' in body
    assert 'name="ret-TOTAL_FORMS"' in body
    assert 'id="id_ret-TOTAL_FORMS"' in body
    assert 'hx-swap-oob="true"' in body
    assert 'value="1"' in body
