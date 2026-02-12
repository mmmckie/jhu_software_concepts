import importlib.util
import sys
import types
import builtins
from pathlib import Path

import pytest

# Ensure `board` is importable regardless of where pytest is launched.
MODULE_4_ROOT = Path(__file__).resolve().parents[1]
if str(MODULE_4_ROOT) not in sys.path:
    sys.path.insert(0, str(MODULE_4_ROOT))

pytestmark = pytest.mark.web


def _fake_results():
    return {
        "total_records": 1,
        "fall_2026_applicants": 1,
        "international_percentage": 50.0,
        "american_fall_2026_gpa": 3.8,
        "fall_2025_acceptance_rate": 25.0,
        "fall_2026_acceptance_gpa": 3.9,
        "jhu_cs_masters": 1,
        "ivy_2026_compsci_phds": 1,
        "ivy_2026_compsci_phds_llm_fields": 1,
        "ivy_2026_compsci_phds_raw_fields": 1,
        "fall_2025_applicants": 1,
        "spring_2025_applicants": 1,
        "masters_acceptance": {"with_gpa": 10.0, "no_gpa": 5.0},
        "phd_acceptance": {"with_gpa": 20.0, "no_gpa": 10.0},
        "average_metrics": {
            "gpa": 3.7,
            "gre": 165.0,
            "gre_v": 160.0,
            "gre_aw": 4.5,
        },
    }


@pytest.fixture
def app():
    query_data_stub = types.ModuleType("query_data")
    query_data_stub.run_analysis = _fake_results
    main_stub = types.ModuleType("main")
    main_stub.update_new_records = lambda: {"status": "no_new", "records": 0}

    sys.modules["query_data"] = query_data_stub
    sys.modules["main"] = main_stub

    from board import create_app

    app = create_app()
    app.config.update(TESTING=True)
    yield app

    sys.modules.pop("query_data", None)
    sys.modules.pop("main", None)


@pytest.fixture
def client(app):
    return app.test_client()


def test_analysis_page_renders_error_when_analysis_raises(client, monkeypatch):
    """Ensure non-API analysis page renders error text when analysis fails."""
    import board.pages as pages

    monkeypatch.setattr(pages, "run_analysis", lambda: (_ for _ in ()).throw(RuntimeError("analysis failed")))

    response = client.get("/analysis")

    assert response.status_code == 200
    page = response.get_data(as_text=True)
    assert "Error loading analysis:" in page
    assert "analysis failed" in page


def test_pull_non_api_busy_returns_409_with_info_message(client, monkeypatch):
    """Ensure non-API pull returns 409 with busy informational message."""
    import board.pages as pages

    monkeypatch.setattr(pages, "_PULL_IN_PROGRESS", True)

    response = client.post("/pull")

    assert response.status_code == 409
    page = response.get_data(as_text=True)
    assert "Pull Data is already running. Please wait for it to finish." in page


def test_pull_non_api_success_returns_html(client, monkeypatch):
    """Ensure non-API pull success returns HTML with pull-in-progress guidance."""
    import board.pages as pages

    monkeypatch.setattr(pages, "_PULL_IN_PROGRESS", False)
    monkeypatch.setattr(pages, "update_new_records", lambda: {"status": "updated", "records": 2})
    monkeypatch.setattr(pages, "run_analysis", _fake_results)

    response = client.post("/pull", follow_redirects=True)

    assert response.status_code == 200
    page = response.get_data(as_text=True)
    assert "Pull Data is currently running. Update Analysis will work once it finishes." in page


def test_pull_non_api_error_returns_html(client, monkeypatch):
    """Ensure non-API pull failure still returns HTML response with status guidance."""
    import board.pages as pages

    monkeypatch.setattr(pages, "_PULL_IN_PROGRESS", False)
    monkeypatch.setattr(pages, "update_new_records", lambda: (_ for _ in ()).throw(RuntimeError("loader failed html")))

    response = client.post("/pull", follow_redirects=True)

    assert response.status_code == 200
    page = response.get_data(as_text=True)
    assert "Pull Data is currently running. Update Analysis will work once it finishes." in page


def test_update_non_api_busy_returns_409_with_info_message(client, monkeypatch):
    """Ensure non-API update during pull is blocked and message is shown."""
    import board.pages as pages

    monkeypatch.setattr(pages, "_PULL_IN_PROGRESS", True)

    response = client.post("/update", follow_redirects=True)

    assert response.status_code == 200
    page = response.get_data(as_text=True)
    assert "Pull Data is currently running. Update Analysis will work once it finishes." in page
    assert "Analysis updated with the latest available data." not in page


def test_update_button_renders_disabled_while_pull_in_progress(client, monkeypatch):
    """Ensure Update Analysis button is disabled while pull is in progress."""
    import board.pages as pages

    monkeypatch.setattr(pages, "_PULL_IN_PROGRESS", True)

    response = client.get("/analysis")

    assert response.status_code == 200
    page = response.get_data(as_text=True)
    assert 'data-testid="update-analysis-btn" disabled' in page


def test_update_non_api_success_returns_html(client, monkeypatch):
    """Ensure non-API update success renders confirmation message."""
    import board.pages as pages

    monkeypatch.setattr(pages, "_PULL_IN_PROGRESS", False)
    monkeypatch.setattr(pages, "run_analysis", _fake_results)

    response = client.post("/update")

    assert response.status_code == 200
    page = response.get_data(as_text=True)
    assert "Analysis updated with the latest available data." in page


def test_update_non_api_error_returns_html(client, monkeypatch):
    """Ensure non-API update failure renders HTML error details."""
    import board.pages as pages

    monkeypatch.setattr(pages, "_PULL_IN_PROGRESS", False)
    monkeypatch.setattr(pages, "run_analysis", lambda: (_ for _ in ()).throw(RuntimeError("update failed html")))

    response = client.post("/update")

    assert response.status_code == 200
    page = response.get_data(as_text=True)
    assert "Error loading analysis:" in page
    assert "update failed html" in page


def test_update_api_error_returns_500_json(client, monkeypatch):
    """Ensure API update endpoint returns structured 500 JSON on failures."""
    import board.pages as pages

    monkeypatch.setattr(pages, "_PULL_IN_PROGRESS", False)
    monkeypatch.setattr(pages, "run_analysis", lambda: (_ for _ in ()).throw(RuntimeError("update failed api")))

    response = client.post("/update-analysis")

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
        if name in {"query_data", "main"}:
            raise ModuleNotFoundError(name)
        if name == "src.query_data":
            return fake_src_query
        if name == "src.main":
            return fake_src_main
        return real_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", fake_import)

    spec = importlib.util.spec_from_file_location("board_pages_fallback_under_test", pages_path)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None
    assert spec.loader is not None

    spec.loader.exec_module(module)

    assert module.run_analysis() == {"from": "src.query_data"}
    assert module.update_new_records() == {"status": "from-src-main", "records": 0}
