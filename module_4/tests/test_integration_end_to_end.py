import sys
import types
from pathlib import Path

import pytest

# Ensure `board` is importable regardless of where pytest is launched.
MODULE_4_ROOT = Path(__file__).resolve().parents[1]
if str(MODULE_4_ROOT) not in sys.path:
    sys.path.insert(0, str(MODULE_4_ROOT))

pytestmark = pytest.mark.integration


class FakeAdmissionsDB:
    def __init__(self):
        self._rows = []
        self._urls = set()

    def count(self):
        return len(self._rows)

    @property
    def rows(self):
        return list(self._rows)

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


class FakeScraper:
    def __init__(self, batches):
        self._batches = list(batches)
        self.calls = 0

    def pull(self):
        self.calls += 1
        if not self._batches:
            return []
        return self._batches.pop(0)


def _analysis_from_db(db):
    total = db.count()
    fall_2026 = sum(1 for r in db.rows if r.get("term") == "Fall 2026")
    international = sum(1 for r in db.rows if r.get("US/International") == "International")
    intl_pct = round((international / total) * 100, 2) if total else 0.0

    fall_2025 = [r for r in db.rows if r.get("term") == "Fall 2025"]
    accepted_fall_2025 = sum(1 for r in fall_2025 if r.get("application status") == "Accepted")
    fall_2025_acceptance = round((accepted_fall_2025 / len(fall_2025)) * 100, 2) if fall_2025 else 0.0

    return {
        "total_records": total,
        "fall_2026_applicants": fall_2026,
        "international_percentage": intl_pct,
        "american_fall_2026_gpa": 3.75,
        "fall_2025_acceptance_rate": fall_2025_acceptance,
        "fall_2026_acceptance_gpa": 3.85,
        "jhu_cs_masters": 1,
        "ivy_2026_compsci_phds": 1,
        "ivy_2026_compsci_phds_llm_fields": 1,
        "ivy_2026_compsci_phds_raw_fields": 1,
        "fall_2025_applicants": len(fall_2025),
        "spring_2025_applicants": sum(1 for r in db.rows if r.get("term") == "Spring 2025"),
        "average_metrics": {"gpa": 3.7, "gre": 165.0, "gre_v": 160.0, "gre_aw": 4.5},
        "masters_acceptance": {"with_gpa": 10.0, "no_gpa": 4.2},
        "phd_acceptance": {"with_gpa": 15.5, "no_gpa": 8.0},
    }


def _batch_one():
    return [
        {
            "url": "https://www.thegradcafe.com/result/300001",
            "university": "Johns Hopkins University",
            "program": "Computer Science",
            "term": "Fall 2026",
            "degree": "Masters",
            "application status": "Accepted",
            "US/International": "International",
        },
        {
            "url": "https://www.thegradcafe.com/result/300002",
            "university": "MIT",
            "program": "Computer Science",
            "term": "Fall 2025",
            "degree": "PhD",
            "application status": "Accepted",
            "US/International": "American",
        },
        {
            "url": "https://www.thegradcafe.com/result/300003",
            "university": "Stanford University",
            "program": "Computer Science",
            "term": "Fall 2026",
            "degree": "PhD",
            "application status": "Rejected",
            "US/International": "International",
        },
    ]


def _batch_two_with_overlap():
    return [
        {
            "url": "https://www.thegradcafe.com/result/300003",  # overlap from batch one
            "university": "Stanford University",
            "program": "Computer Science",
            "term": "Fall 2026",
            "degree": "PhD",
            "application status": "Rejected",
            "US/International": "International",
        },
        {
            "url": "https://www.thegradcafe.com/result/300004",
            "university": "CMU",
            "program": "Computer Science",
            "term": "Spring 2025",
            "degree": "Masters",
            "application status": "Accepted",
            "US/International": "American",
        },
    ]


@pytest.fixture
def app():
    query_data_stub = types.ModuleType("query_data")
    query_data_stub.run_analysis = lambda: {}
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


def test_end_to_end_pull_update_render(client, monkeypatch):
    """Verify end-to-end pull then update flow populates and renders analysis."""
    import board.pages as pages

    fake_db = FakeAdmissionsDB()
    fake_scraper = FakeScraper([_batch_one()])

    def fake_update_new_records():
        rows = fake_scraper.pull()
        inserted = fake_db.insert_rows(rows)
        if inserted == 0:
            return {"status": "no_new", "records": 0}
        return {"status": "updated", "records": inserted}

    monkeypatch.setattr(pages, "_PULL_IN_PROGRESS", False)
    monkeypatch.setattr(pages, "update_new_records", fake_update_new_records)
    monkeypatch.setattr(pages, "run_analysis", lambda: _analysis_from_db(fake_db))

    pull_response = client.post("/pull-data")
    assert pull_response.status_code == 200
    assert pull_response.get_json()["ok"] is True
    assert fake_db.count() == 3

    update_response = client.post("/update-analysis")
    assert update_response.status_code == 200
    assert update_response.get_json()["ok"] is True

    analysis_response = client.get("/analysis")
    assert analysis_response.status_code == 200
    page = analysis_response.get_data(as_text=True)

    assert "Analysis" in page
    assert "Answer:" in page
    assert "66.67%" in page
    assert "100.00%" in page
    assert pull_response.get_json()["records"] == 3


def test_multiple_pulls_with_overlapping_data_follow_uniqueness_policy(client, monkeypatch):
    """Verify repeated pulls honor uniqueness constraints across overlapping data."""
    import board.pages as pages

    fake_db = FakeAdmissionsDB()
    fake_scraper = FakeScraper([_batch_one(), _batch_two_with_overlap()])

    def fake_update_new_records():
        rows = fake_scraper.pull()
        inserted = fake_db.insert_rows(rows)
        if inserted == 0:
            return {"status": "no_new", "records": 0}
        return {"status": "updated", "records": inserted}

    monkeypatch.setattr(pages, "_PULL_IN_PROGRESS", False)
    monkeypatch.setattr(pages, "update_new_records", fake_update_new_records)
    monkeypatch.setattr(pages, "run_analysis", lambda: _analysis_from_db(fake_db))

    first = client.post("/pull-data")
    assert first.status_code == 200
    assert first.get_json()["ok"] is True
    assert fake_db.count() == 3

    second = client.post("/pull-data")
    assert second.status_code == 200
    assert second.get_json()["ok"] is True
    assert fake_db.count() == 4
    assert second.get_json()["records"] == 1
