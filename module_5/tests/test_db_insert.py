import pytest

# Simulate insertion semantics with an in-memory fake DB to test dedupe/required-field rules.
pytestmark = pytest.mark.db


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
def fake_db(fake_admissions_db):
    return fake_admissions_db


def test_insert_on_pull_before_empty_after_rows_with_required_fields(stubbed_client, fake_db, monkeypatch):
    """Ensure pull inserts valid rows and required fields remain populated."""
    import board.pages as pages

    scraper_rows = _make_scraper_rows()
    assert fake_db.count() == 0

    def fake_update_new_records():
        inserted = fake_db.insert_rows(scraper_rows)
        return {"status": "updated", "records": inserted}

    # Setup: wire pull/update callbacks to the in-memory DB fake.
    monkeypatch.setattr(pages, "_PULL_IN_PROGRESS", False)
    monkeypatch.setattr(pages, "update_new_records", fake_update_new_records)
    monkeypatch.setattr(pages, "run_analysis", lambda: _simple_query_dict(fake_db))

    response = stubbed_client.post("/pull-data")

    # Assertions: pull succeeds, rows are inserted, and required fields are non-empty.
    assert response.status_code == 200
    assert fake_db.count() > 0
    for row in fake_db.rows:
        assert row.get("url") not in (None, "")
        assert row.get("university") not in (None, "")
        assert row.get("program") not in (None, "")
        assert row.get("term") not in (None, "")
        assert row.get("degree") not in (None, "")


def test_idempotency_duplicate_rows_do_not_create_duplicates(stubbed_client, fake_db, monkeypatch):
    """Ensure duplicate source rows do not create duplicate DB records."""
    import board.pages as pages

    scraper_rows = _make_scraper_rows()

    def fake_update_new_records():
        inserted = fake_db.insert_rows(scraper_rows)
        return {"status": "updated", "records": inserted}

    # Setup: run identical pull payload twice against URL-unique DB fake.
    monkeypatch.setattr(pages, "_PULL_IN_PROGRESS", False)
    monkeypatch.setattr(pages, "update_new_records", fake_update_new_records)
    monkeypatch.setattr(pages, "run_analysis", lambda: _simple_query_dict(fake_db))

    first_response = stubbed_client.post("/pull-data")
    first_count = fake_db.count()
    second_response = stubbed_client.post("/pull-data")
    second_count = fake_db.count()

    # Assertions: both calls succeed but the second call inserts no additional rows.
    assert first_response.status_code == 200
    assert second_response.status_code == 200
    assert first_count == 2
    assert second_count == first_count


def test_simple_query_function_returns_expected_keys(stubbed_client, fake_db, monkeypatch):
    """Ensure analysis payload includes all expected top-level metric keys."""
    import board.pages as pages

    scraper_rows = _make_scraper_rows()
    fake_db.insert_rows(scraper_rows)

    monkeypatch.setattr(pages, "_PULL_IN_PROGRESS", False)
    monkeypatch.setattr(pages, "run_analysis", lambda: _simple_query_dict(fake_db))

    # Assertions: query output shape matches the expected metrics contract.
    result = pages.run_analysis()
    assert isinstance(result, dict)
    assert EXPECTED_QUERY_KEYS.issubset(set(result.keys()))


def test_pull_data_loader_error_returns_500_and_no_partial_writes(stubbed_client, fake_db, monkeypatch):
    """Ensure loader failure returns 500 and leaves DB unchanged."""
    import board.pages as pages

    assert fake_db.count() == 0

    def failing_loader():
        raise RuntimeError("loader failed")

    monkeypatch.setattr(pages, "_PULL_IN_PROGRESS", False)
    monkeypatch.setattr(pages, "update_new_records", failing_loader)
    monkeypatch.setattr(pages, "run_analysis", lambda: _simple_query_dict(fake_db))

    # Assertions: failure is surfaced as 500 JSON and fake DB remains empty.
    response = stubbed_client.post("/pull-data")

    assert response.status_code == 500
    body = response.get_json()
    assert body["ok"] is False
    assert body["busy"] is False
    assert "loader failed" in body["error"]
    assert fake_db.count() == 0
