Testing Guide
=============

Marker policy
-------------

Every test is required to have at least one approved marker:

- ``web``
- ``buttons``
- ``analysis``
- ``db``
- ``integration``

This is enforced at collection time by ``tests/conftest.py``.

Run test groups
---------------

From ``jhu_software_concepts/module_5``:

.. code-block:: bash

   pytest -m "web or buttons or analysis or db or integration"

Run a single marker:

.. code-block:: bash

   pytest -m web
   pytest -m buttons

Expected UI selectors
---------------------

UI tests expect these stable attributes in ``analysis.html``:

- ``data-testid="pull-data-btn"``
- ``data-testid="update-analysis-btn"``

If these selectors change, update tests in:

- ``tests/test_flask_page.py``
- ``tests/test_pages_non_api.py``

Fixtures and test doubles
-------------------------

Common fixtures:

- ``app`` and ``client`` fixtures in several test modules
- Flask ``TESTING=True`` configuration via app factory

Common doubles/mocks used by the suite:

- ``FakeAdmissionsDB`` and ``FakeScraper`` for integration/db behavior
- ``FakeCursor`` and ``FakeConn`` for DB-adjacent unit tests
- ``monkeypatch`` for swapping services/functions and environment variables
- ``sys.modules`` stubs for import-path and main-guard testing

Coverage target
---------------

Pytest configuration enforces 100% coverage:

.. code-block:: bash

   pytest -q --cov=src --cov-report=term-missing --cov-fail-under=100
