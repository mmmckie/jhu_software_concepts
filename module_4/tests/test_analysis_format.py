import re
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
        "total_records": 12,
        "fall_2026_applicants": 5,
        "international_percentage": 7,
        "american_fall_2026_gpa": 3.81,
        "fall_2025_acceptance_rate": 2.5,
        "fall_2026_acceptance_gpa": 3.91,
        "jhu_cs_masters": 3,
        "ivy_2026_compsci_phds": 2,
        "ivy_2026_compsci_phds_llm_fields": 1,
        "ivy_2026_compsci_phds_raw_fields": 1,
        "fall_2025_applicants": 9,
        "spring_2025_applicants": 3,
        "masters_acceptance": {"with_gpa": 10, "no_gpa": 4.2},
        "phd_acceptance": {"with_gpa": 15.5, "no_gpa": 8},
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


def test_analysis_page_includes_answer_labels(client):
    response = client.get("/analysis")
    assert response.status_code == 200

    page = response.get_data(as_text=True)
    assert "Answer:" in page


def test_percentages_are_formatted_with_two_decimals(client):
    response = client.get("/analysis")
    assert response.status_code == 200

    page = response.get_data(as_text=True)
    percentages = re.findall(r"\b\d+\.\d{2}%", page)

    assert "7.00%" in page
    assert "2.50%" in page
    assert "10.00%" in page
    assert "4.20%" in page
    assert "15.50%" in page
    assert "8.00%" in page
    assert len(percentages) >= 6
