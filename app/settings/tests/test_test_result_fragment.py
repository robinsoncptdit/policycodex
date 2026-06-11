from django.template.loader import render_to_string


def test_ok_result_green():
    html = render_to_string("settings/_test_result.html", {
        "result": {"state": "ok", "message": "Connected."},
    })
    assert "alert-success" in html
    assert "Connected." in html
    assert 'data-state="ok"' in html


def test_error_result_red():
    html = render_to_string("settings/_test_result.html", {
        "result": {"state": "error", "message": "401 Bad credentials"},
    })
    assert "alert-error" in html
    assert "401 Bad credentials" in html
    assert 'data-state="error"' in html
