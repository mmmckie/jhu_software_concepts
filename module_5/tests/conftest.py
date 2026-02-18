import pytest
import sys
import types
from pathlib import Path

# Enforce marker discipline so each test maps to a documented suite category.
ALLOWED_MARKERS = {"web", "buttons", "analysis", "db", "integration"}

# Keep `board` importable when pytest is launched from different working dirs.
MODULE_4_ROOT = Path(__file__).resolve().parents[1]
if str(MODULE_4_ROOT) not in sys.path:
    sys.path.insert(0, str(MODULE_4_ROOT))


@pytest.fixture
def fake_results_payload():
    """Shared deterministic analysis payload for web-layer tests."""
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
def stubbed_app(fake_results_payload):
    """Create Flask app with deterministic query/load stubs."""
    query_data_stub = types.ModuleType("query_data")
    query_data_stub.run_analysis = lambda: fake_results_payload
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
def stubbed_client(stubbed_app):
    """Create test client from the shared stubbed app."""
    return stubbed_app.test_client()


class FakeAdmissionsDB:
    """In-memory DB fake that enforces required-field and URL-uniqueness rules."""

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


@pytest.fixture
def fake_admissions_db():
    """Provide a fresh in-memory admissions fake per test."""
    return FakeAdmissionsDB()


def pytest_collection_modifyitems(session, config, items):
    unmarked = []
    for item in items:
        # Accept tests carrying any one approved marker; multiple markers are also valid.
        if not ALLOWED_MARKERS.intersection(item.keywords):
            unmarked.append(item.nodeid)

    if unmarked:
        # Fail collection early so CI does not run partially categorized suites.
        joined = "\n".join(f"- {nodeid}" for nodeid in unmarked)
        raise pytest.UsageError(
            "Each test must include at least one approved marker "
            f"({', '.join(sorted(ALLOWED_MARKERS))}).\n"
            "Unmarked tests:\n"
            f"{joined}"
        )
