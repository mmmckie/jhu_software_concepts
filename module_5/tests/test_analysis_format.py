import re

import pytest

# Validate output formatting rules independently from data-ingestion mechanics.
pytestmark = pytest.mark.analysis


def test_analysis_page_includes_answer_labels(stubbed_client):
    """Ensure the rendered analysis page includes answer label text."""
    # Setup: fetch one rendered page from the shared stubbed client.
    response = stubbed_client.get("/analysis")
    # Assertions: verify response is successful and expected label text is present.
    assert response.status_code == 200

    # Ensure at least one 'Answer:' field is present
    page = response.get_data(as_text=True)
    assert "Answer:" in page


def test_percentages_are_formatted_with_two_decimals(stubbed_client):
    """Ensure percentage fields are rendered with two decimal places."""
    # Setup: fetch one page and reuse it for all format checks.
    response = stubbed_client.get("/analysis")
    assert response.status_code == 200
    
    page = response.get_data(as_text=True)
    # Regex intentionally targets rendered percentage tokens, not raw numeric values.
    percentages = re.findall(r"\b\d+\.\d{2}%", page)

    # Assertions: every displayed percentage should be normalized to two decimal places.
    assert "7.00%" in page # International percentage
    assert "2.50%" in page # Fall 2025 Acceptance Rate
    assert "10.00%" in page # Master's acceptance with GPA
    assert "4.20%" in page # Master's acceptance no GPA
    assert "15.50%" in page # PhD acceptance with GPA
    assert "8.00%" in page # PhD acceptance with GPA
    assert len(percentages) >= 6 # All percentage fields are present
