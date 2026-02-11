import sys
import types
from pathlib import Path

import pytest

# Ensure `board` is importable regardless of where pytest is launched.
MODULE_4_ROOT = Path(__file__).resolve().parents[1]
if str(MODULE_4_ROOT) not in sys.path:
    sys.path.insert(0, str(MODULE_4_ROOT))


EXPECTED_QUERY_KEYS = {
    "total_records",
    "fall_2026_applicants",
    "international_percentage",
    "american_fall_2026_gpa",
    "fall_2025_acceptance_rate",
    "fall_2026_acceptance_gpa",
    "jhu_cs_masters",
    "ivy_2026_compsci_phds",
    "ivy_2026_compsci_phds_llm_fields",
    "ivy_2026_compsci_phds_raw_fields",
    "fall_2025_applicants",
    "spring_2025_applicants",
    "average_metrics",
    "masters_acceptance",
    "phd_acceptance",
}


class FakeAdmissionsDB:
    def __init__(self):
        self._rows = []
        self._urls = set()

    @property
    def rows(self):
        return list(self._rows)

    def count(self):
        return len(self._rows)

    def insert_rows(self, rows):
        required_fields = ("url", "university", "program", "term", "degree")
        inserted = 0
        for row in rows:
            if any(row.get(field) in (None, "") for field in required_fields):
                continue
            url = row["url"]
            if url in self._urls:
                continue
            self._urls.add(url)
            self._rows.append(row)
            inserted += 1
        return inserted


def _make_scraper_rows():
    # Includes one duplicate URL and one invalid row to test constraints/required fields.
    return [
        {
            "url": "https://www.thegradcafe.com/result/100001",
            "university": "Johns Hopkins University",
            "program": "Computer Science",
            "term": "Fall 2026",
            "degree": "Masters",
            "application status": "Accepted",
            "US/International": "American",
            "GPA": 3.9,
        },
        {
            "url": "https://www.thegradcafe.com/result/100002",
            "university": "MIT",
            "program": "Computer Science",
            "term": "Fall 2026",
            "degree": "PhD",
            "application status": "Accepted",
            "US/International": "International",
            "GPA": 3.8,
        },
        {
            "url": "https://www.thegradcafe.com/result/100002",  # duplicate
            "university": "MIT",
            "program": "Computer Science",
            "term": "Fall 2026",
            "degree": "PhD",
            "application status": "Accepted",
            "US/International": "International",
            "GPA": 3.8,
        },
        {
            "url": "https://www.thegradcafe.com/result/100003",  # invalid (missing program)
            "university": "Stanford University",
            "program": "",
            "term": "Fall 2026",
            "degree": "PhD",
            "application status": "Rejected",
            "US/International": "International",
            "GPA": 3.7,
        },
    ]


def _simple_query_dict(db):
    total = db.count()
    fall_2026 = sum(1 for r in db.rows if r.get("term") == "Fall 2026")
    international = sum(1 for r in db.rows if r.get("US/International") == "International")
    pct_international = round((international / total) * 100, 2) if total else 0.0

    return {
        "total_records": total,
        "fall_2026_applicants": fall_2026,
        "international_percentage": pct_international,
        "american_fall_2026_gpa": 0.0,
        "fall_2025_acceptance_rate": 0.0,
        "fall_2026_acceptance_gpa": 0.0,
        "jhu_cs_masters": 0,
        "ivy_2026_compsci_phds": 0,
        "ivy_2026_compsci_phds_llm_fields": 0,
        "ivy_2026_compsci_phds_raw_fields": 0,
        "fall_2025_applicants": 0,
        "spring_2025_applicants": 0,
        "average_metrics": {"gpa": 0.0, "gre": 0.0, "gre_v": 0.0, "gre_aw": 0.0},
        "masters_acceptance": {"with_gpa": 0.0, "no_gpa": 0.0},
        "phd_acceptance": {"with_gpa": 0.0, "no_gpa": 0.0},
    }


@pytest.fixture
def app():
    query_data_stub = types.ModuleType("query_data")
    query_data_stub.run_analysis = lambda: _simple_query_dict(FakeAdmissionsDB())
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


@pytest.fixture
def fake_db():
    return FakeAdmissionsDB()


def test_insert_on_pull_before_empty_after_rows_with_required_fields(client, fake_db, monkeypatch):
    import board.pages as pages

    scraper_rows = _make_scraper_rows()
    assert fake_db.count() == 0

    def fake_update_new_records():
        inserted = fake_db.insert_rows(scraper_rows)
        return {"status": "updated", "records": inserted}

    monkeypatch.setattr(pages, "_PULL_IN_PROGRESS", False)
    monkeypatch.setattr(pages, "update_new_records", fake_update_new_records)
    monkeypatch.setattr(pages, "run_analysis", lambda: _simple_query_dict(fake_db))

    response = client.post("/pull-data")

    assert response.status_code == 200
    assert fake_db.count() > 0
    for row in fake_db.rows:
        assert row.get("url") not in (None, "")
        assert row.get("university") not in (None, "")
        assert row.get("program") not in (None, "")
        assert row.get("term") not in (None, "")
        assert row.get("degree") not in (None, "")


def test_idempotency_duplicate_rows_do_not_create_duplicates(client, fake_db, monkeypatch):
    import board.pages as pages

    scraper_rows = _make_scraper_rows()

    def fake_update_new_records():
        inserted = fake_db.insert_rows(scraper_rows)
        return {"status": "updated", "records": inserted}

    monkeypatch.setattr(pages, "_PULL_IN_PROGRESS", False)
    monkeypatch.setattr(pages, "update_new_records", fake_update_new_records)
    monkeypatch.setattr(pages, "run_analysis", lambda: _simple_query_dict(fake_db))

    first_response = client.post("/pull-data")
    first_count = fake_db.count()
    second_response = client.post("/pull-data")
    second_count = fake_db.count()

    assert first_response.status_code == 200
    assert second_response.status_code == 200
    assert first_count == 2
    assert second_count == first_count


def test_simple_query_function_returns_expected_keys(client, fake_db, monkeypatch):
    import board.pages as pages

    scraper_rows = _make_scraper_rows()
    fake_db.insert_rows(scraper_rows)

    monkeypatch.setattr(pages, "_PULL_IN_PROGRESS", False)
    monkeypatch.setattr(pages, "run_analysis", lambda: _simple_query_dict(fake_db))

    result = pages.run_analysis()
    assert isinstance(result, dict)
    assert EXPECTED_QUERY_KEYS.issubset(set(result.keys()))
