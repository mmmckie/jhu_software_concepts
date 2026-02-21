import pytest
from tests.test_doubles import FakeConn, FakeCursor

# End-to-end integration uses deterministic fakes to verify workflow coordination.
pytestmark = pytest.mark.integration


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


def test_end_to_end_pull_update_render(stubbed_client, fake_admissions_db, monkeypatch):
    """Verify end-to-end pull then update flow populates and renders analysis."""
    import board.pages as pages

    # Setup: seed scraper with one batch and route inserts into fake admissions DB.
    fake_db = fake_admissions_db
    fake_scraper = FakeScraper([_batch_one()])

    def fake_update_new_records():
        rows = fake_scraper.pull()
        inserted = fake_db.insert_rows(rows)
        # Mimic service contract used by API route handler in `pages.analysis_pull`.
        if inserted == 0:
            return {"status": "no_new", "records": 0}
        return {"status": "updated", "records": inserted}

    monkeypatch.setattr(pages, "_PULL_IN_PROGRESS", False)
    monkeypatch.setattr(pages, "update_new_records", fake_update_new_records)
    monkeypatch.setattr(pages, "run_analysis", lambda: _analysis_from_db(fake_db))

    # Exercise full flow: pull -> update -> render analysis page.
    pull_response = stubbed_client.post("/pull-data")
    assert pull_response.status_code == 200
    assert pull_response.get_json()["ok"] is True
    assert fake_db.count() == 3

    update_response = stubbed_client.post("/update-analysis")
    assert update_response.status_code == 200
    assert update_response.get_json()["ok"] is True

    analysis_response = stubbed_client.get("/analysis")
    assert analysis_response.status_code == 200
    page = analysis_response.get_data(as_text=True)

    # Assertions: metrics are rendered and pull status reports inserted record count.
    assert "Analysis" in page
    assert "Answer:" in page
    assert "66.67%" in page
    assert "100.00%" in page
    assert pull_response.get_json()["records"] == 3


def test_multiple_pulls_with_overlapping_data_follow_uniqueness_policy(stubbed_client, fake_admissions_db, monkeypatch):
    """Verify repeated pulls honor uniqueness constraints across overlapping data."""
    import board.pages as pages

    # Setup: provide two batches where the second includes one overlapping URL.
    fake_db = fake_admissions_db
    fake_scraper = FakeScraper([_batch_one(), _batch_two_with_overlap()])

    def fake_update_new_records():
        rows = fake_scraper.pull()
        inserted = fake_db.insert_rows(rows)
        # Overlapping batches should only report genuinely new inserts.
        if inserted == 0:
            return {"status": "no_new", "records": 0}
        return {"status": "updated", "records": inserted}

    monkeypatch.setattr(pages, "_PULL_IN_PROGRESS", False)
    monkeypatch.setattr(pages, "update_new_records", fake_update_new_records)
    monkeypatch.setattr(pages, "run_analysis", lambda: _analysis_from_db(fake_db))

    # Assertions: first pull inserts baseline rows, second pull inserts only new row.
    first = stubbed_client.post("/pull-data")
    assert first.status_code == 200
    assert first.get_json()["ok"] is True
    assert fake_db.count() == 3

    second = stubbed_client.post("/pull-data")
    assert second.status_code == 200
    assert second.get_json()["ok"] is True
    assert fake_db.count() == 4
    assert second.get_json()["records"] == 1


def test_pull_data_route_executes_postgres_loader_path(stubbed_client, monkeypatch, tmp_path):
    """Verify `/pull-data` drives the loader path that performs PostgreSQL inserts."""
    import json
    import board.pages as pages
    import load_data

    record = {
        "university": "MIT",
        "program": "Computer Science",
        "comments": "test row",
        "date added": "January 1, 2026",
        "url": "https://www.thegradcafe.com/result/999001",
        "application status": "Accepted",
        "term": "Fall 2026",
        "US/International": "International",
        "GPA": "3.9",
        "GRE": "165",
        "GRE V": "160",
        "GRE AW": "4.5",
        "degree": "PhD",
        "llm-generated-program": "Computer Science",
        "llm-generated-university": "MIT",
    }
    # Setup: create one valid JSONL record that should pass loader validation and insert.
    jsonl_path = tmp_path / "route_loader_input.jsonl"
    jsonl_path.write_text(json.dumps(record) + "\n", encoding="utf-8")

    fake_cursor = FakeCursor()
    fake_conn = FakeConn(fake_cursor)

    # Setup: replace DB provisioning/connect calls so we can assert SQL/commit behavior in-memory.
    monkeypatch.setattr(load_data, "create_db_if_not_exists", lambda: None)
    monkeypatch.setattr(load_data.psycopg, "connect", lambda *args, **kwargs: fake_conn)

    def fake_update_new_records():
        # Setup: route handler calls this service; keep real loader logic under controlled DB fakes.
        load_data.stream_jsonl_to_postgres(str(jsonl_path))
        return {"status": "updated", "records": 1}

    monkeypatch.setattr(pages, "_PULL_IN_PROGRESS", False)
    monkeypatch.setattr(pages, "update_new_records", fake_update_new_records)
    # Setup: analysis result is irrelevant to this test; provide a minimal stub payload.
    monkeypatch.setattr(pages, "run_analysis", lambda: {})

    response = stubbed_client.post("/pull-data")

    # Assertions: API contract reports success and inserted-record count from service response.
    assert response.status_code == 200
    body = response.get_json()
    assert body["ok"] is True
    assert body["records"] == 1
    # Assertions: loader executed write-path behavior (transaction commit + schema/insert SQL).
    assert fake_conn.committed is True
    assert any("CREATE TABLE IF NOT EXISTS admissions" in str(q) for q, _ in fake_cursor.executed)
    assert any("INSERT INTO admissions" in str(q) for q, _ in fake_cursor.executed)
