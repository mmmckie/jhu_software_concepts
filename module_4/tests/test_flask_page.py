import sys
import types
from pathlib import Path

import pytest
from bs4 import BeautifulSoup
from flask import Flask

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


def test_app_factory_creates_testable_app_with_required_routes(app):
    assert isinstance(app, Flask)
    assert app.config["TESTING"] is True

    routes = {rule.rule for rule in app.url_map.iter_rules()}
    assert "/" in routes
    assert "/analysis" in routes
    assert "/pull" in routes
    assert "/update" in routes


def test_get_analysis_page_loads_expected_content(client):
    response = client.get("/analysis")

    assert response.status_code == 200
    page = response.get_data(as_text=True)
    soup = BeautifulSoup(page, "html.parser")
    assert "Analysis" in soup.get_text(" ")

    pull_btn = soup.select_one('[data-testid="pull-data-btn"]')
    update_btn = soup.select_one('[data-testid="update-analysis-btn"]')
    assert pull_btn is not None
    assert update_btn is not None
    assert pull_btn.get_text(strip=True) == "Pull Data"
    assert update_btn.get_text(strip=True) == "Update Analysis"
    assert soup.find(string=lambda s: s and "Answer:" in s) is not None
