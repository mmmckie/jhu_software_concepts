Operational Notes
=================

Busy-state policy
-----------------

- ``POST /pull`` and ``POST /pull-data`` set a shared in-progress flag while pull/load work is running.
- ``POST /update`` and ``POST /update-analysis`` are blocked during that window.
- API callers receive ``409`` with ``{"busy": true, "ok": false}`` when gated.
- Browser callers are redirected/rendered with a user-facing message instead of JSON.

Idempotency strategy
--------------------

- Pull operations may be retried safely.
- Duplicate source rows are tolerated by database-level conflict handling.
- The load path uses ``ON CONFLICT (url) DO NOTHING`` for inserts.

Uniqueness keys
---------------

- The canonical uniqueness key is ``admissions.url``.
- A unique index is maintained on ``url`` to prevent duplicate records.
- Incremental pulls can reuse existing URLs and max result-page values to reduce reprocessing.

Troubleshooting
---------------

- ``psycopg.OperationalError`` on startup: verify PostgreSQL is running and ``DATABASE_URL`` is correct.
- Empty page metrics after pull: confirm loader wrote rows and ``/update-analysis`` completed without ``409 busy``.
- Marker-related collection failures: ensure every test has at least one allowed marker in ``pytest.ini``.
- CI-only failures: check service Postgres health/readiness and environment variables in workflow config.
