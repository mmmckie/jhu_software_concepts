import json
import runpy
import subprocess
import sys
import types
from pathlib import Path

import pytest

pytestmark = [pytest.mark.analysis, pytest.mark.integration]

MODULE_4_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = MODULE_4_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))


def _sample_payload(term="Fall 2026"):
    return {
        "university": "MIT\n",
        "program": "CS\t",
        "degree": "PhD",
        "term": f"\n{term}\n",
        "date added": "January 28, 2026",
        "url": "https://www.thegradcafe.com/result/1",
        "application status": "Accepted",
        "application status date": "on 01/28/2026 via email",
        "comments": "",
        "US/International": "International",
        "GPA": "0.00",
        "GRE": "0",
        "GRE V": "0",
        "GRE AW": "0.00",
    }


def test_clean_remove_whitespace_and_clean_data_branches():
    import clean

    assert clean._remove_whitespace("a\nb\tc") == "abc"

    raw = [_sample_payload(term="Fall 2026"), _sample_payload(term="Spring 2025")]
    raw[1]["comments"] = "kept"
    raw[1]["GPA"] = "3.80"
    raw[1]["GRE"] = "165"
    raw[1]["GRE V"] = "160"
    raw[1]["GRE AW"] = "4.0"

    cleaned = clean.clean_data(raw)
    assert len(cleaned) == 2
    assert cleaned[0]["term"] == "Fall 2026"
    assert cleaned[1]["term"] == "Spring 2025"
    assert cleaned[0]["application status date"] == "01/28/2026"
    assert cleaned[0]["comments"] is None
    assert cleaned[0]["GPA"] is None
    assert cleaned[0]["GRE"] is None
    assert cleaned[0]["GRE V"] is None
    assert cleaned[0]["GRE AW"] is None
    assert cleaned[1]["comments"] == "kept"


def test_clean_save_and_load_data(tmp_path, monkeypatch):
    import clean

    data = [{"x": 1}, {"x": 2}]
    out_path = tmp_path / "sample.json"
    clean.save_data(data, str(out_path))
    assert json.loads(out_path.read_text()) == data

    monkeypatch.chdir(tmp_path)
    (tmp_path / "applicant_data.json").write_text(json.dumps(data))
    assert clean.load_data() == data


def test_main_run_llm_pipeline_success_and_error(tmp_path, monkeypatch, capsys):
    import main

    monkeypatch.chdir(tmp_path)

    called = {"ok": False}

    def fake_run_ok(cmd, cwd, stdout, check):
        called["ok"] = True
        assert cmd[:2] == ["python", "app.py"]
        assert cwd == "llm_hosting"
        assert check is True

    monkeypatch.setattr(main.subprocess, "run", fake_run_ok)
    main._run_LLM_pipeline("applicant_data.json", "out.jsonl")
    assert called["ok"] is True
    assert "Pipeline executed successfully!" in capsys.readouterr().out

    def fake_run_fail(*args, **kwargs):
        raise subprocess.CalledProcessError(returncode=3, cmd="x")

    monkeypatch.setattr(main.subprocess, "run", fake_run_fail)
    main._run_LLM_pipeline("applicant_data.json", "out2.jsonl")
    assert "failed with error code: 3" in capsys.readouterr().out


def test_main_append_helpers_and_main_flow(tmp_path, monkeypatch):
    import main

    monkeypatch.chdir(tmp_path)

    # _append_json_records branch: file exists but non-list payload
    j = tmp_path / "full.json"
    j.write_text(json.dumps({"bad": "shape"}))
    main._append_json_records([{"a": 1}], j)
    assert json.loads(j.read_text()) == [{"a": 1}]

    # _append_json_records branch: file missing
    j2 = tmp_path / "new.json"
    main._append_json_records([{"a": 2}], j2)
    assert json.loads(j2.read_text()) == [{"a": 2}]

    # _append_jsonl_records branch: blank lines are skipped
    src = tmp_path / "in.jsonl"
    dst = tmp_path / "out.jsonl"
    src.write_text('\n{"a":1}\n\n{"a":2}\n')
    main._append_jsonl_records(src, dst)
    assert dst.read_text() == '{"a":1}\n{"a":2}\n'

    flow = []
    monkeypatch.setattr(main, "scrape_data", lambda: [{"x": 1}])
    monkeypatch.setattr(main, "clean_data", lambda raw: [{"y": raw[0]["x"]}])
    monkeypatch.setattr(main, "save_data", lambda data, path: flow.append(("save", path, data)))
    monkeypatch.setattr(main, "_run_LLM_pipeline", lambda i, o: flow.append(("llm", i, o)))
    main.main()
    assert ("save", "applicant_data.json", [{"y": 1}]) in flow
    assert ("llm", "applicant_data.json", "llm_extend_applicant_data.jsonl") in flow


def test_main_update_new_records_no_new_and_updated(tmp_path, monkeypatch):
    import main

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(main, "get_existing_urls", lambda: {"u1"})
    monkeypatch.setattr(main, "get_max_result_page", lambda: 10)

    # no_new branch
    monkeypatch.setattr(main, "scrape_data", lambda **kwargs: [])
    assert main.update_new_records() == {"status": "no_new"}

    # updated branch
    calls = []
    monkeypatch.setattr(main, "scrape_data", lambda **kwargs: [{"url": "u2"}])
    monkeypatch.setattr(main, "clean_data", lambda raw: [{"cleaned": True}])
    monkeypatch.setattr(main, "save_data", lambda data, path: calls.append(("save", path)))
    monkeypatch.setattr(main, "_run_LLM_pipeline", lambda i, o: calls.append(("llm", i, o)))
    monkeypatch.setattr(main, "_append_json_records", lambda r, p: calls.append(("append_json", p)))
    monkeypatch.setattr(main, "_append_jsonl_records", lambda s, t: calls.append(("append_jsonl", s, t)))
    monkeypatch.setattr(main, "stream_jsonl_to_postgres", lambda p: calls.append(("stream", p)))
    out = main.update_new_records()
    assert out == {"status": "updated", "records": 1}
    assert ("save", "applicant_data_new.json") in calls
    assert ("stream", "llm_extend_applicant_data_new.jsonl") in calls


def test_main_module_main_guard_executes(monkeypatch):
    fake_scrape = types.ModuleType("scrape")
    fake_scrape.scrape_data = lambda: []
    fake_clean = types.ModuleType("clean")
    fake_clean.clean_data = lambda raw: raw
    fake_clean.save_data = lambda data, path: None
    fake_clean.load_data = lambda: []
    fake_load = types.ModuleType("load_data")
    fake_load.stream_jsonl_to_postgres = lambda path: None
    fake_load.get_existing_urls = lambda: set()
    fake_load.get_max_result_page = lambda: None

    monkeypatch.setitem(sys.modules, "scrape", fake_scrape)
    monkeypatch.setitem(sys.modules, "clean", fake_clean)
    monkeypatch.setitem(sys.modules, "load_data", fake_load)

    called = {"n": 0}

    class FakeSubprocess(types.SimpleNamespace):
        @staticmethod
        def run(*args, **kwargs):
            called["n"] += 1

    monkeypatch.setitem(sys.modules, "subprocess", FakeSubprocess())

    tests_dir = MODULE_4_ROOT / "tests"
    generated_json = tests_dir / "applicant_data.json"
    generated_jsonl = tests_dir / "llm_extend_applicant_data.jsonl"
    generated_json.unlink(missing_ok=True)
    generated_jsonl.unlink(missing_ok=True)

    monkeypatch.chdir(tests_dir)
    runpy.run_path(str(SRC_ROOT / "main.py"), run_name="__main__")

    # Running main.py as a script writes relative outputs in the current CWD.
    assert generated_jsonl.exists()
    generated_json.unlink(missing_ok=True)
    generated_jsonl.unlink(missing_ok=True)
    assert called["n"] == 1
