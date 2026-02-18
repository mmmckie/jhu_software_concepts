import importlib.util
import types
import builtins
from pathlib import Path

import pytest

# Focus on browser-style (non-JSON) route behavior and user-facing error states.
MODULE_4_ROOT = Path(__file__).resolve().parents[1]

pytestmark = pytest.mark.web


def test_analysis_page_renders_error_when_analysis_raises(stubbed_client, monkeypatch):
    """Ensure non-API analysis page renders error text when analysis fails."""
    import board.pages as pages

    monkeypatch.setattr(pages, "run_analysis", lambda: (_ for _ in ()).throw(RuntimeError("analysis failed")))

    # Setup: force analysis service to raise and request browser route.
    response = stubbed_client.get("/analysis")

    # Assertions: non-API flow still renders HTML and includes the failure message.
    assert response.status_code == 200
    page = response.get_data(as_text=True)
    assert "Error loading analysis:" in page
    assert "analysis failed" in page


def test_pull_non_api_busy_returns_409_with_info_message(stubbed_client, monkeypatch):
    """Ensure non-API pull returns 409 with busy informational message."""
    import board.pages as pages

    monkeypatch.setattr(pages, "_PULL_IN_PROGRESS", True)

    # Setup: mark pull as in-progress before posting to browser pull route.
    response = stubbed_client.post("/pull")

    # Assertions: conflict HTML is returned with user-facing busy guidance.
    assert response.status_code == 409
    page = response.get_data(as_text=True)
    assert "Pull Data is already running. Please wait for it to finish." in page


def test_pull_non_api_success_returns_html(stubbed_client, monkeypatch, fake_results_payload):
    """Ensure non-API pull success returns HTML with pull-in-progress guidance."""
    import board.pages as pages

    monkeypatch.setattr(pages, "_PULL_IN_PROGRESS", False)
    monkeypatch.setattr(pages, "update_new_records", lambda: {"status": "updated", "records": 2})
    monkeypatch.setattr(pages, "run_analysis", lambda: fake_results_payload)

    # Setup: emulate successful pull path and follow redirect back to analysis page.
    response = stubbed_client.post("/pull", follow_redirects=True)

    # Assertions: resulting HTML shows pull-in-progress informational banner.
    assert response.status_code == 200
    page = response.get_data(as_text=True)
    assert "Pull Data is currently running. Update Analysis will work once it finishes." in page


def test_pull_non_api_error_returns_html(stubbed_client, monkeypatch):
    """Ensure non-API pull failure still returns HTML response with status guidance."""
    import board.pages as pages

    monkeypatch.setattr(pages, "_PULL_IN_PROGRESS", False)
    monkeypatch.setattr(pages, "update_new_records", lambda: (_ for _ in ()).throw(RuntimeError("loader failed html")))

    # Setup: emulate failing loader in browser pull flow.
    response = stubbed_client.post("/pull", follow_redirects=True)

    # Assertions: page still renders and preserves busy/info guidance for user continuity.
    assert response.status_code == 200
    page = response.get_data(as_text=True)
    assert "Pull Data is currently running. Update Analysis will work once it finishes." in page


def test_update_non_api_busy_returns_409_with_info_message(stubbed_client, monkeypatch):
    """Ensure non-API update during pull is blocked and message is shown."""
    import board.pages as pages

    monkeypatch.setattr(pages, "_PULL_IN_PROGRESS", True)

    # Setup: trigger update while pull is marked busy and follow redirect.
    response = stubbed_client.post("/update", follow_redirects=True)

    # Assertions: busy banner appears and success banner is absent.
    assert response.status_code == 200
    page = response.get_data(as_text=True)
    assert "Pull Data is currently running. Update Analysis will work once it finishes." in page
    assert "Analysis updated with the latest available data." not in page


def test_update_button_renders_disabled_while_pull_in_progress(stubbed_client, monkeypatch):
    """Ensure Update Analysis button is disabled while pull is in progress."""
    import board.pages as pages

    monkeypatch.setattr(pages, "_PULL_IN_PROGRESS", True)

    # Setup: render analysis page during busy pull state.
    response = stubbed_client.get("/analysis")

    # Assertions: update button is rendered with `disabled` attribute.
    assert response.status_code == 200
    page = response.get_data(as_text=True)
    assert 'data-testid="update-analysis-btn" disabled' in page


def test_update_non_api_success_returns_html(stubbed_client, monkeypatch, fake_results_payload):
    """Ensure non-API update success renders confirmation message."""
    import board.pages as pages

    monkeypatch.setattr(pages, "_PULL_IN_PROGRESS", False)
    monkeypatch.setattr(pages, "run_analysis", lambda: fake_results_payload)

    # Setup: allow update path to execute analysis successfully.
    response = stubbed_client.post("/update")

    # Assertions: HTML includes explicit update confirmation text.
    assert response.status_code == 200
    page = response.get_data(as_text=True)
    assert "Analysis updated with the latest available data." in page


def test_update_non_api_error_returns_html(stubbed_client, monkeypatch):
    """Ensure non-API update failure renders HTML error details."""
    import board.pages as pages

    monkeypatch.setattr(pages, "_PULL_IN_PROGRESS", False)
    monkeypatch.setattr(pages, "run_analysis", lambda: (_ for _ in ()).throw(RuntimeError("update failed html")))

    # Setup: emulate analysis failure in non-API update flow.
    response = stubbed_client.post("/update")

    # Assertions: rendered HTML exposes error banner and original error text.
    assert response.status_code == 200
    page = response.get_data(as_text=True)
    assert "Error loading analysis:" in page
    assert "update failed html" in page


def test_update_api_error_returns_500_json(stubbed_client, monkeypatch):
    """Ensure API update endpoint returns structured 500 JSON on failures."""
    import board.pages as pages

    monkeypatch.setattr(pages, "_PULL_IN_PROGRESS", False)
    monkeypatch.setattr(pages, "run_analysis", lambda: (_ for _ in ()).throw(RuntimeError("update failed api")))

    # Setup: emulate failure in API update route.
    response = stubbed_client.post("/update-analysis")

    # Assertions: API response is 500 with structured error payload.
    assert response.status_code == 500
    body = response.get_json()
    assert body["busy"] is False
    assert body["ok"] is False
    assert "update failed api" in body["error"]


def test_pages_import_uses_src_fallback_when_top_level_modules_missing(monkeypatch):
    """Ensure pages module fallback imports from ``src.*`` when top-level imports fail."""
    pages_path = MODULE_4_ROOT / "src" / "board" / "pages.py"

    fake_src_query = types.ModuleType("src.query_data")
    fake_src_query.run_analysis = lambda: {"from": "src.query_data"}
    fake_src_main = types.ModuleType("src.main")
    fake_src_main.update_new_records = lambda: {"status": "from-src-main", "records": 0}
    real_import = builtins.__import__

    def fake_import(name, globals=None, locals=None, fromlist=(), level=0):
        # Force the first import attempt to fail so the module executes fallback branches.
        if name in {"query_data", "main"}:
            raise ModuleNotFoundError(name)
        if name == "src.query_data":
            return fake_src_query
        if name == "src.main":
            return fake_src_main
        return real_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", fake_import)

    # Setup: load module by path so import-time fallback code executes in isolation.
    spec = importlib.util.spec_from_file_location("board_pages_fallback_under_test", pages_path)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None
    assert spec.loader is not None

    spec.loader.exec_module(module)

    # Assertions: resolved functions come from the fallback `src.*` modules.
    assert module.run_analysis() == {"from": "src.query_data"}
    assert module.update_new_records() == {"status": "from-src-main", "records": 0}
