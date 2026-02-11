import sys
import types
from pathlib import Path

import pytest

# Ensure `board` is importable regardless of where pytest is launched.
MODULE_4_ROOT = Path(__file__).resolve().parents[1]
if str(MODULE_4_ROOT) not in sys.path:
    sys.path.insert(0, str(MODULE_4_ROOT))


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


def test_post_pull_data_returns_200_and_triggers_loader(client, monkeypatch):
    import board.pages as pages

    calls = {"loader": 0, "analysis": 0}

    def fake_loader():
        calls["loader"] += 1
        return {"status": "updated", "records": 3}

    def fake_analysis():
        calls["analysis"] += 1
        return _fake_results()

    monkeypatch.setattr(pages, "_PULL_IN_PROGRESS", False)
    monkeypatch.setattr(pages, "update_new_records", fake_loader)
    monkeypatch.setattr(pages, "run_analysis", fake_analysis)

    response = client.post("/pull-data")

    assert response.status_code == 200
    assert calls["loader"] == 1
    assert calls["analysis"] == 1


def test_post_update_analysis_returns_200_when_not_busy(client, monkeypatch):
    import board.pages as pages

    calls = {"analysis": 0}

    def fake_analysis():
        calls["analysis"] += 1
        return _fake_results()

    monkeypatch.setattr(pages, "_PULL_IN_PROGRESS", False)
    monkeypatch.setattr(pages, "run_analysis", fake_analysis)

    response = client.post("/update-analysis")

    assert response.status_code == 200
    assert calls["analysis"] == 1


def test_busy_gating_update_returns_409_and_does_not_update(client, monkeypatch):
    import board.pages as pages

    calls = {"analysis": 0}

    def fake_analysis():
        calls["analysis"] += 1
        return _fake_results()

    monkeypatch.setattr(pages, "_PULL_IN_PROGRESS", True)
    monkeypatch.setattr(pages, "run_analysis", fake_analysis)

    response = client.post("/update-analysis")

    assert response.status_code == 409
    assert "Pull Data is currently running" in response.get_data(as_text=True)
    assert calls["analysis"] == 0


def test_busy_gating_pull_returns_409_and_does_not_trigger_loader(client, monkeypatch):
    import board.pages as pages

    calls = {"loader": 0, "analysis": 0}

    def fake_loader():
        calls["loader"] += 1
        return {"status": "updated", "records": 3}

    def fake_analysis():
        calls["analysis"] += 1
        return _fake_results()

    monkeypatch.setattr(pages, "_PULL_IN_PROGRESS", True)
    monkeypatch.setattr(pages, "update_new_records", fake_loader)
    monkeypatch.setattr(pages, "run_analysis", fake_analysis)

    response = client.post("/pull-data")

    assert response.status_code == 409
    assert "Pull Data is already running" in response.get_data(as_text=True)
    assert calls["loader"] == 0
    assert calls["analysis"] == 0
