import io
import runpy
import sys
import types
from pathlib import Path
from urllib import error

import pytest

# Validates scraping helpers plus script-entry behavior with network/process fakes.
pytestmark = [pytest.mark.web, pytest.mark.integration]

MODULE_4_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = MODULE_4_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))


class DummyResponse:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self):
        return self.payload


def test_scrape_fetch_table_and_result_pages(monkeypatch, capsys):
    """Validate table/result scraping success paths and handled fetch failures."""
    import scrape

    # Setup: validate restricted-path helper first, then drive network/parsing branches with fakes.
    assert scrape._is_restricted_path("https://x/cgi-bin/a")
    assert not scrape._is_restricted_path("https://x/survey/?page=1")

    # Restricted paths should immediately short-circuit network work.
    monkeypatch.setattr(scrape, "_is_restricted_path", lambda url: True)
    assert scrape._fetch_table_page(1) == []
    assert scrape._fetch_result_page("https://x/result/1", {}) == {}

    # Re-enable normal flow and then test HTML parsing branches.
    monkeypatch.setattr(scrape, "_is_restricted_path", lambda url: False)

    table_html = b"""
    <html><body><table>
      <tr><th>h</th></tr>
      <tr><td><a href="/result/11">L</a></td><td>a</td><td>b</td><td>January 1, 2026</td><td>x</td><td>y</td><td>Fall 2026</td></tr>
      <tr class="alt"><td>cont</td></tr>
    </table></body></html>
    """
    monkeypatch.setattr(scrape, "urlopen", lambda req, timeout=10: DummyResponse(table_html))
    rows = scrape._fetch_table_page(1)
    # Assertions: table parser returns row groups and preserves result URL field.
    assert rows and rows[0][0] == "/result/11"

    result_html = b"""
    <html><body><dl>
      <div><dd>MIT</dd></div>
      <div><dd>CS</dd></div>
      <div><dd>PhD</dd></div>
      <div><dd>International</dd></div>
      <div><dd>Accepted</dd></div>
      <div><dd>01/01/2026</dd></div>
      <div><dd>3.90</dd></div>
      <div><dd><ul><li><span>Q</span>: <b>165</b></li><li><span>V</span>: <b>160</b></li><li><span>AW</span>: <b>4.5</b></li></ul></dd></div>
      <div><dd>comment</dd></div>
    </dl></body></html>
    """
    monkeypatch.setattr(scrape, "urlopen", lambda req, timeout=10: DummyResponse(result_html))
    payload = scrape._fetch_result_page("https://x/result/12", {})
    # Assertions: result parser extracts core fields and GRE subfields correctly.
    assert payload["university"] == "MIT"
    assert payload["GRE"] == "165"
    assert payload["GRE V"] == "160"
    assert payload["GRE AW"] == "4.5"

    empty_result_html = b"<html><body><dl></dl></body></html>"
    monkeypatch.setattr(scrape, "urlopen", lambda req, timeout=10: DummyResponse(empty_result_html))
    assert scrape._fetch_result_page("https://x/result/13", {}) == {}

    def raise_http(*args, **kwargs):
        raise error.HTTPError("u", 500, "err", hdrs=None, fp=None)

    monkeypatch.setattr(scrape, "urlopen", raise_http)
    assert scrape._fetch_table_page(2) == []
    assert scrape._fetch_result_page("https://x/result/14", {}) == {}
    # Assertions: HTTP errors are handled without raising and produce logged message.
    assert "HTTP Error 500" in capsys.readouterr().out

    def raise_generic(*args, **kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(scrape, "urlopen", raise_generic)
    assert scrape._fetch_table_page(3) == []
    assert scrape._fetch_result_page("https://x/result/15", {}) == {}

    # Assertions: result-number extraction handles valid, invalid, and None inputs.
    assert scrape._extract_result_num("https://x/result/123") == 123
    assert scrape._extract_result_num("https://x/result/not-int") is None
    assert scrape._extract_result_num(None) is None


def test_scrape_concurrency_get_payloads_and_filtering(monkeypatch):
    """Validate concurrency helper behavior and scrape-data filtering logic."""
    import scrape

    # Setup: exercise concurrent worker helper in both list and mapping modes.
    # _concurrent_scraper for list returns + exception path
    def worker_list(x):
        if x == 2:
            raise ValueError("bad")
        return [x]

    out = scrape._concurrent_scraper(worker_list, [1, 2, 3])
    # Assertions: failed tasks are skipped while successful results are returned.
    assert sorted(out) == [1, 3]

    # _concurrent_scraper with mapping: verifies 2-arg worker submission path.
    payload_map = {"u1": {"seed": 1}, "u2": {"seed": 2}}
    out2 = scrape._concurrent_scraper(lambda url, payload: {"url": url, **payload}, list(payload_map.keys()), is_mapping=True, all_payloads=payload_map)
    assert len(out2) == 2

    # _get_raw_payloads handles malformed row via except
    monkeypatch.setattr(scrape, "_concurrent_scraper", lambda *args, **kwargs: [{"ok": True}])
    payloads = scrape._get_raw_payloads([["/result/1", "a", "b", "Jan 1", "x", "y", "Fall 2026"], ["bad"]])
    assert payloads == [{"ok": True}]

    # scrape_data filtering: first run applies min_result_num + existing URL filters.
    rows = [
        ["/result/10", "a", "b", "Jan 1", "x", "y", "Fall 2026"],
        ["/result/20", "a", "b", "Jan 1", "x", "y", "Fall 2026"],
        [],
    ]
    monkeypatch.setattr(scrape, "_concurrent_scraper", lambda *args, **kwargs: rows)
    monkeypatch.setattr(scrape, "_get_raw_payloads", lambda rows_in: rows_in)
    # Use a fixed clock to avoid flaky runtime-print assertions if added later.
    monkeypatch.setattr(scrape.time, "time", lambda: 0.0)
    filtered = scrape.scrape_data(min_result_num=15, existing_urls={scrape.BASE_URL + "/result/20"})
    # Assertions: filter removes old/known rows under min-result and existing-url constraints.
    assert filtered == []

    monkeypatch.setattr(scrape, "_concurrent_scraper", lambda *args, **kwargs: rows)
    monkeypatch.setattr(scrape, "_get_raw_payloads", lambda rows_in: rows_in)
    all_rows = scrape.scrape_data()
    # Assertions: unfiltered scrape returns all mocked rows.
    assert len(all_rows) == 3


def test_scrape_uncovered_branches_for_table_result_and_filter_append(monkeypatch):
    """Exercise additional scrape branches for coverage-sensitive edge cases."""
    import scrape

    # Setup: use targeted HTML fixtures to hit uncovered parse/filter branches.
    monkeypatch.setattr(scrape, "_is_restricted_path", lambda url: False)

    # No table found branch.
    monkeypatch.setattr(scrape, "urlopen", lambda req, timeout=10: DummyResponse(b"<html><body></body></html>"))
    assert scrape._fetch_table_page(1) == []

    # Append tmp_row when a new record begins and tmp_row already has data.
    table_html_two_records = b"""
    <html><body><table>
      <tr><th>h</th></tr>
      <tr><td><a href="/result/11">L1</a></td><td>a</td><td>b</td><td>January 1, 2026</td><td>x</td><td>y</td><td>Fall 2026</td></tr>
      <tr><td><a href="/result/12">L2</a></td><td>a2</td><td>b2</td><td>January 2, 2026</td><td>x2</td><td>y2</td><td>Spring 2025</td></tr>
    </table></body></html>
    """
    monkeypatch.setattr(scrape, "urlopen", lambda req, timeout=10: DummyResponse(table_html_two_records))
    parsed = scrape._fetch_table_page(2)
    # Assertions: parser emits two distinct row records from consecutive table entries.
    assert len(parsed) == 2
    assert parsed[0][0] == "/result/11"
    assert parsed[1][0] == "/result/12"

    # Missing <dd> for one of the expected indices triggers `continue`.
    result_missing_dd_html = b"""
    <html><body><dl>
      <div><dd>MIT</dd></div>
      <div></div>
      <div><dd>PhD</dd></div>
      <div><dd>International</dd></div>
      <div><dd>Accepted</dd></div>
      <div><dd>01/01/2026</dd></div>
      <div><dd>3.90</dd></div>
      <div><dd><ul><li><span>Q</span>: <b>165</b></li><li><span>V</span>: <b>160</b></li><li><span>AW</span>: <b>4.5</b></li></ul></dd></div>
      <div><dd>comment</dd></div>
    </dl></body></html>
    """
    monkeypatch.setattr(scrape, "urlopen", lambda req, timeout=10: DummyResponse(result_missing_dd_html))
    payload = scrape._fetch_result_page("https://x/result/22", {})
    # Assertions: missing `<dd>` skips that field but retains other parsed values.
    assert payload["university"] == "MIT"
    assert "program" not in payload

    # filtered_rows.append(row) branch in scrape_data filtering path.
    rows = [["/result/30", "a", "b", "Jan 1", "x", "y", "Fall 2026"]]
    monkeypatch.setattr(scrape, "_concurrent_scraper", lambda *args, **kwargs: rows)
    monkeypatch.setattr(scrape, "_get_raw_payloads", lambda rows_in: rows_in)
    kept = scrape.scrape_data(min_result_num=10, existing_urls=set())
    # Assertions: qualifying row is retained by filter append branch.
    assert kept == rows


def test_run_module_main_guard(monkeypatch):
    """Validate ``run.py`` script guard boots app and calls ``app.run``."""
    # Setup: replace `board.create_app` with a fake app that records `.run()` calls.
    fake_board = types.ModuleType("board")

    class FakeApp:
        def __init__(self):
            self.ran = False

        def run(self, **kwargs):
            self.ran = True

    app = FakeApp()
    fake_board.create_app = lambda: app
    monkeypatch.setitem(sys.modules, "board", fake_board)

    # Assertions: script guard exposes `app` and invokes the fake app runner.
    out = runpy.run_path(str(SRC_ROOT / "run.py"), run_name="__main__")
    assert "app" in out
    assert app.ran is True
