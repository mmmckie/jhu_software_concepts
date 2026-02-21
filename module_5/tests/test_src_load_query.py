import json
import importlib
import runpy
import sys
import types
from pathlib import Path

import pytest
from tests.test_doubles import FakeConn, FakeCursor

# Uses lightweight DB fakes to verify loader/query behavior across success and failure paths.
pytestmark = [pytest.mark.db, pytest.mark.analysis]

MODULE_4_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = MODULE_4_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))


def test_load_data_helpers_and_stream_jsonl(monkeypatch, tmp_path, capsys):
    """Validate DB helper branches and JSONL-to-Postgres ingest behavior."""
    import load_data

    # Setup: swap psycopg connections with fakes to exercise each helper branch in isolation.
    # create_db_if_not_exists: DB missing branch issues CREATE DATABASE.
    c1 = FakeCursor(fetchone_values=[None])
    conn1 = FakeConn(c1)
    monkeypatch.setattr(load_data.psycopg, "connect", lambda *args, **kwargs: conn1)
    load_data.create_db_if_not_exists()
    assert any("CREATE DATABASE" in str(q) for q, _ in c1.executed)

    # create_db_if_not_exists: existing DB branch prints status only.
    c2 = FakeCursor(fetchone_values=[(1,)])
    conn2 = FakeConn(c2)
    monkeypatch.setattr(load_data.psycopg, "connect", lambda *args, **kwargs: conn2)
    load_data.create_db_if_not_exists()
    assert "already exists" in capsys.readouterr().out

    # get_max_result_page: covers value, null, and exception fallbacks.
    c3 = FakeCursor(fetchone_values=[(99,)])
    monkeypatch.setattr(load_data.psycopg, "connect", lambda *args, **kwargs: FakeConn(c3))
    assert load_data.get_max_result_page() == 99

    c4 = FakeCursor(fetchone_values=[(None,)])
    monkeypatch.setattr(load_data.psycopg, "connect", lambda *args, **kwargs: FakeConn(c4))
    assert load_data.get_max_result_page() is None

    def raise_connect(*args, **kwargs):
        raise RuntimeError("db down")

    monkeypatch.setattr(load_data.psycopg, "connect", raise_connect)
    assert load_data.get_max_result_page() is None
    assert load_data.get_existing_urls() == set()

    # get_existing_urls: empty/null URLs are filtered out.
    c5 = FakeCursor(fetchall_values=[[("u1",), ("",), (None,), ("u2",)]])
    monkeypatch.setattr(load_data.psycopg, "connect", lambda *args, **kwargs: FakeConn(c5))
    assert load_data.get_existing_urls() == {"u1", "u2"}

    # format_date: valid, invalid, and missing inputs.
    assert load_data.format_date(None) is None
    assert str(load_data.format_date("January 28, 2026")) == "2026-01-28"
    assert load_data.format_date("not-a-date") is None

    # stream_jsonl_to_postgres: blank and incomplete lines are skipped.
    lines = [
        "",
        json.dumps({"university": "", "url": "https://x/result/1"}) + "\n",
        json.dumps(
            {
                "university": "MIT",
                "program": "CS",
                "comments": None,
                "date added": "January 28, 2026",
                "url": "https://x/result/123",
                "application status": "Accepted",
                "term": "Fall 2026",
                "US/International": "American",
                "GPA": "3.9",
                "GRE": "165",
                "GRE V": "160",
                "GRE AW": "4.5",
                "degree": "PhD",
                "llm-generated-program": "Computer Science",
                "llm-generated-university": "MIT",
            }
        )
        + "\n",
    ]
    p = tmp_path / "in.jsonl"
    p.write_text("\n".join(lines))

    stream_cursor = FakeCursor()
    stream_conn = FakeConn(stream_cursor)
    calls = {"createdb": 0}

    def fake_connect(*args, **kwargs):
        return stream_conn

    monkeypatch.setattr(load_data.psycopg, "connect", fake_connect)
    # Replace DB bootstrap with a counter so test stays focused on ingest behavior.
    monkeypatch.setattr(load_data, "create_db_if_not_exists", lambda: calls.__setitem__("createdb", 1))
    load_data.stream_jsonl_to_postgres(str(p))
    # Assertions: ingest path bootstraps DB, creates schema, inserts data, and commits once.
    assert calls["createdb"] == 1
    assert stream_conn.committed is True
    assert any("CREATE TABLE IF NOT EXISTS admissions" in str(q) for q, _ in stream_cursor.executed)
    assert any("INSERT INTO admissions" in str(q) for q, _ in stream_cursor.executed)


def test_database_url_env_override(monkeypatch):
    """Ensure explicit ``DATABASE_URL`` bypasses auto DB creation logic."""
    # Setup: define explicit DB URL and reload modules to pick up env-driven connection info.
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@host:5432/testdb")

    import load_data
    import query_data

    importlib.reload(load_data)
    importlib.reload(query_data)

    # Assertions: modules use explicit connection string and skip admin bootstrap connect.
    assert load_data.conn_info == "postgresql://user:pass@host:5432/testdb"
    assert query_data.conn_info == "postgresql://user:pass@host:5432/testdb"
    monkeypatch.setattr(load_data.psycopg, "connect", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("should not connect")))
    load_data.create_db_if_not_exists()

    monkeypatch.delenv("DATABASE_URL", raising=False)
    importlib.reload(load_data)
    importlib.reload(query_data)


def test_provision_schema_raises_when_database_url_set(monkeypatch):
    """Ensure admin-provision path is blocked when DATABASE_URL is explicitly set."""
    import load_data

    monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@host:5432/testdb")

    with pytest.raises(RuntimeError, match="admissions table is missing"):
        load_data._provision_admissions_schema()

    monkeypatch.delenv("DATABASE_URL", raising=False)


def test_provision_schema_creates_table_and_grants(monkeypatch):
    """Ensure schema provisioning executes DDL and least-privilege grants."""
    import load_data

    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("DB_USER", "grad_app")

    c = FakeCursor()
    conn = FakeConn(c)
    monkeypatch.setattr(load_data.psycopg, "connect", lambda *args, **kwargs: conn)

    load_data._provision_admissions_schema()

    assert conn.committed is True
    assert any("CREATE TABLE IF NOT EXISTS admissions" in str(q) for q, _ in c.executed)
    assert any("CREATE UNIQUE INDEX IF NOT EXISTS admissions_url_key" in str(q) for q, _ in c.executed)
    assert any("GRANT USAGE ON SCHEMA public" in str(q) for q, _ in c.executed)
    assert any("GRANT SELECT, INSERT, UPDATE ON TABLE public.admissions" in str(q) for q, _ in c.executed)
    assert any("GRANT USAGE, SELECT ON SEQUENCE public.admissions_p_id_seq" in str(q) for q, _ in c.executed)


def test_load_data_main_guard(monkeypatch, tmp_path):
    """Validate ``load_data.py`` script guard executes ingest flow."""
    # Setup: fake psycopg and input file so script guard can run without real DB/filesystem deps.
    fake_psycopg = types.ModuleType("psycopg")

    class Ctx(FakeConn):
        pass

    c = FakeCursor()
    fake_psycopg.connect = lambda *args, **kwargs: Ctx(c)
    monkeypatch.setitem(sys.modules, "psycopg", fake_psycopg)
    (tmp_path / "llm_extend_applicant_data.jsonl").write_text("")
    monkeypatch.chdir(tmp_path)
    # Assertions: running script guard attempts schema creation and/or inserts.
    runpy.run_path(str(SRC_ROOT / "load_data.py"), run_name="__main__")
    assert any(
        "INSERT INTO admissions" in str(q) or "CREATE TABLE IF NOT EXISTS admissions" in str(q)
        for q, _ in c.executed
    )


def test_get_existing_urls_paginates_until_empty_batch(monkeypatch):
    """Ensure URL fetch loops across pages and exits on empty terminal batch."""
    import load_data

    first_batch = [(f"u{i}",) for i in range(100)]
    c = FakeCursor(fetchall_values=[first_batch, []])
    monkeypatch.setattr(load_data.psycopg, "connect", lambda *args, **kwargs: FakeConn(c))

    urls = load_data.get_existing_urls()

    assert len(urls) == 100
    assert len(c.executed) == 2


def test_query_data_run_analysis_and_execute_query_error(monkeypatch):
    """Validate query aggregation outputs and execute_query error wrapping."""
    import query_data
    real_execute_query = query_data.execute_query

    # Setup: feed canned query results to simulate complete analytics pipeline responses.
    responses = iter(
        [
            [(10,)],
            [(7,)],
            [(4,)],
            [(3.7, 165.0, 160.0, 4.5)],
            [(3.8,)],
            [(55.55,)],
            [(3.9,)],
            [(2,)],
            [(1,)],
            [(1,)],
            [(1,)],
            [(1, 2)],
            [("Reported GPA", 1, 88.0), ("No GPA", 2, 50.0)],
            [("Reported GPA", 1, 77.0), ("No GPA", 1, 25.0)],
        ]
    )

    monkeypatch.setattr(query_data, "execute_query", lambda q: next(responses))
    # Assertions: nominal aggregation output fields are computed from canned rows.
    out = query_data.run_analysis()
    assert out["total_records"] == 10
    assert out["international_percentage"] == 40.0
    assert out["average_metrics"]["gpa"] == 3.7
    assert out["masters_acceptance"]["with_gpa"] == 88.0
    assert out["phd_acceptance"]["no_gpa"] == 25.0

    responses2 = iter(
        [
            [(0,)],
            [(0,)],
            [(0,)],
            [(0.0, 0.0, 0.0, 0.0)],
            [(None,)],
            [(None,)],
            [(None,)],
            [(0,)],
            [(0,)],
            [(0,)],
            [(0,)],
            [(0, 0)],
            [],
            [],
        ]
    )
    monkeypatch.setattr(query_data, "execute_query", lambda q: next(responses2))
    # Assertions: zero-data path produces safe defaults and `None` for missing groups.
    out2 = query_data.run_analysis()
    assert out2["international_percentage"] == 0.0
    assert out2["masters_acceptance"]["with_gpa"] is None

    def fail_connect(*args, **kwargs):
        raise ValueError("boom")

    monkeypatch.setattr(query_data, "execute_query", real_execute_query)
    monkeypatch.setattr(query_data.psycopg, "connect", fail_connect)
    # Assertions: raw DB exception is wrapped by `execute_query` as RuntimeError.
    with pytest.raises(RuntimeError):
        query_data.execute_query(query_data.sql.SQL("SELECT 1"))


def test_query_data_execute_query_rejects_raw_sql_and_binds_limit(monkeypatch):
    """Validate execute_query rejects raw strings and appends bound limit param."""
    import query_data

    with pytest.raises(RuntimeError, match="Query must be psycopg.sql.Composable"):
        query_data.execute_query("SELECT 1")

    c = FakeCursor(fetchall_values=[[(1,)]])
    monkeypatch.setattr(query_data.psycopg, "connect", lambda *args, **kwargs: FakeConn(c))

    out = query_data.execute_query(query_data.sql.SQL("SELECT %s"), params=(1,), limit=1000)
    assert out == [(1,)]
    assert c.executed[0][1] == (1, 100)


def test_query_data_main_guard(monkeypatch, capsys):
    """Validate ``query_data.py`` script guard prints expected summary lines."""
    # Setup: fake psycopg responses so `query_data.py` can execute as a script deterministically.
    fake_psycopg = types.ModuleType("psycopg")

    class QCursor(FakeCursor):
        def execute(self, query, params=None):
            super().execute(query, params)

    class QConn(FakeConn):
        pass

    # Provide one fetchall payload per execute_query call made by run_analysis().
    fetchall_values = [
        [(10,)],
        [(7,)],
        [(4,)],
        [(3.7, 165.0, 160.0, 4.5)],
        [(3.8,)],
        [(55.55,)],
        [(3.9,)],
        [(2,)],
        [(1,)],
        [(1,)],
        [(1,)],
        [(1, 2)],
        [("Reported GPA", 1, 88.0), ("No GPA", 2, 50.0)],
        [("Reported GPA", 1, 77.0), ("No GPA", 1, 25.0)],
    ]
    c = QCursor(fetchall_values=fetchall_values)
    fake_psycopg.connect = lambda *args, **kwargs: QConn(c)
    monkeypatch.setitem(sys.modules, "psycopg", fake_psycopg)

    runpy.run_path(str(SRC_ROOT / "query_data.py"), run_name="__main__")
    stdout = capsys.readouterr().out
    # Assertions: CLI output contains expected summary lines from the computed results.
    assert "There are 10 entries" in stdout
    assert "Fall 2025 Applicants" in stdout
