import pytest

# Exercise POST button actions and verify route-level side effects and status codes.
pytestmark = pytest.mark.buttons


def test_post_pull_data_returns_200_and_triggers_loader(stubbed_client, monkeypatch, fake_results_payload):
    """Verify API pull endpoint runs loader+analysis and returns success JSON."""
    import board.pages as pages

    calls = {"loader": 0, "analysis": 0}
    # Counters verify side effects directly rather than asserting on internal Flask state.

    def fake_loader():
        calls["loader"] += 1
        return {"status": "updated", "records": 3}

    def fake_analysis():
        calls["analysis"] += 1
        return fake_results_payload

    # Setup: patch route dependencies so pull path uses local counters and fake payloads.
    monkeypatch.setattr(pages, "_PULL_IN_PROGRESS", False)
    monkeypatch.setattr(pages, "update_new_records", fake_loader)
    monkeypatch.setattr(pages, "run_analysis", fake_analysis)

    response = stubbed_client.post("/pull-data")

    # Assertions: API contract is success and both loader/analysis callbacks ran once.
    assert response.status_code == 200
    assert response.get_json()["ok"] is True
    assert response.get_json()["busy"] is False
    assert calls["loader"] == 1
    assert calls["analysis"] == 1


def test_post_update_analysis_returns_200_when_not_busy(stubbed_client, monkeypatch, fake_results_payload):
    """Verify API update endpoint executes analysis when pull is not busy."""
    import board.pages as pages

    calls = {"analysis": 0}

    def fake_analysis():
        calls["analysis"] += 1
        return fake_results_payload

    # Setup: force non-busy state so update handler executes analysis callback.
    monkeypatch.setattr(pages, "_PULL_IN_PROGRESS", False)
    monkeypatch.setattr(pages, "run_analysis", fake_analysis)

    response = stubbed_client.post("/update-analysis")

    # Assertions: update returns success JSON and analysis is invoked once.
    assert response.status_code == 200
    assert response.get_json()["ok"] is True
    assert response.get_json()["busy"] is False
    assert calls["analysis"] == 1


def test_busy_gating_update_returns_409_and_does_not_update(stubbed_client, monkeypatch, fake_results_payload):
    """Verify busy-state blocks API update and does not invoke analysis."""
    import board.pages as pages

    calls = {"analysis": 0}

    def fake_analysis():
        calls["analysis"] += 1
        return fake_results_payload

    # Setup: force busy state to exercise early-return guard.
    monkeypatch.setattr(pages, "_PULL_IN_PROGRESS", True)
    monkeypatch.setattr(pages, "run_analysis", fake_analysis)

    response = stubbed_client.post("/update-analysis")

    # Assertions: busy response is 409 and analysis callback is never called.
    assert response.status_code == 409
    assert response.get_json()["busy"] is True
    assert response.get_json()["ok"] is False
    assert calls["analysis"] == 0


def test_busy_gating_pull_returns_409_and_does_not_trigger_loader(stubbed_client, monkeypatch, fake_results_payload):
    """Verify busy-state blocks API pull and does not invoke loader/analysis."""
    import board.pages as pages

    calls = {"loader": 0, "analysis": 0}

    def fake_loader():
        calls["loader"] += 1
        return {"status": "updated", "records": 3}

    def fake_analysis():
        calls["analysis"] += 1
        return fake_results_payload

    # Setup: force busy state so pull handler must reject immediately.
    monkeypatch.setattr(pages, "_PULL_IN_PROGRESS", True)
    monkeypatch.setattr(pages, "update_new_records", fake_loader)
    monkeypatch.setattr(pages, "run_analysis", fake_analysis)

    response = stubbed_client.post("/pull-data")

    # Assertions: conflict response is returned and neither callback executes.
    assert response.status_code == 409
    assert response.get_json()["busy"] is True
    assert response.get_json()["ok"] is False
    assert calls["loader"] == 0
    assert calls["analysis"] == 0


def test_dependency_injection_allows_fake_loader_and_query_without_monkeypatch(fake_results_payload):
    """Verify app-factory dependency injection drives pull endpoint behavior."""
    from board import create_app

    calls = {"loader": 0, "analysis": 0}

    def fake_loader():
        calls["loader"] += 1
        return {"status": "updated", "records": 2}

    def fake_analysis():
        calls["analysis"] += 1
        return fake_results_payload

    app = create_app(
        test_config={"TESTING": True},
        run_analysis_fn=fake_analysis,
        update_new_records_fn=fake_loader,
    )
    # Setup: inject dependencies through `create_app` arguments, not module patching.
    client = app.test_client()

    response = client.post("/pull-data")

    # Assertions: endpoint reflects injected loader result and both callbacks execute.
    assert response.status_code == 200
    body = response.get_json()
    assert body["ok"] is True
    assert body["records"] == 2
    assert calls["loader"] == 1
    assert calls["analysis"] == 1
