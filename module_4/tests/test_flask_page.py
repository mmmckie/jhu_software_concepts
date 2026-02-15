import pytest
from bs4 import BeautifulSoup
from flask import Flask

# These tests validate the rendered HTML contract for the primary analysis page.
pytestmark = pytest.mark.web


@pytest.mark.parametrize("required_route", ["/", "/analysis", "/pull", "/update"])
def test_app_factory_creates_testable_app_with_required_routes(stubbed_app, required_route):
    """Verify the Flask app factory exposes each required core route."""
    # Setup: use shared stubbed app so route-map checks are deterministic.
    assert isinstance(stubbed_app, Flask)
    assert stubbed_app.config["TESTING"] is True

    # Route table verification avoids needing to invoke every route just for existence checks.
    assert stubbed_app.url_map.bind("").match(required_route, method="GET" if required_route in {"/", "/analysis"} else "POST")


def test_get_analysis_page_loads_expected_content(stubbed_client):
    """Validate analysis page load and presence of expected UI controls/content."""
    # Setup: request the rendered analysis page through the Flask test client.
    response = stubbed_client.get("/analysis")

    # Assertions: verify page status and the primary user-facing controls/content.
    assert response.status_code == 200
    page = response.get_data(as_text=True)
    # Parse rendered HTML and assert for concrete UI hooks used by other tests.
    soup = BeautifulSoup(page, "html.parser")
    assert "Analysis" in soup.get_text(" ")

    pull_btn = soup.select_one('[data-testid="pull-data-btn"]')
    update_btn = soup.select_one('[data-testid="update-analysis-btn"]')
    assert pull_btn is not None
    assert update_btn is not None
    assert pull_btn.get_text(strip=True) == "Pull Data"
    assert update_btn.get_text(strip=True) == "Update Analysis"
    assert soup.find(string=lambda s: s and "Answer:" in s) is not None
