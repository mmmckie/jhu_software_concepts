import pytest

ALLOWED_MARKERS = {"web", "buttons", "analysis", "db", "integration"}


def pytest_collection_modifyitems(session, config, items):
    unmarked = []
    for item in items:
        if not ALLOWED_MARKERS.intersection(item.keywords):
            unmarked.append(item.nodeid)

    if unmarked:
        joined = "\n".join(f"- {nodeid}" for nodeid in unmarked)
        raise pytest.UsageError(
            "Each test must include at least one approved marker "
            f"({', '.join(sorted(ALLOWED_MARKERS))}).\n"
            "Unmarked tests:\n"
            f"{joined}"
        )
