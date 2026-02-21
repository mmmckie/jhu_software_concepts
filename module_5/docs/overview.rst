Overview
========

``module_5`` provides:

- A Flask web interface for analysis and pull/update workflows.
- Scraping and cleaning utilities for admissions records.
- Loading/querying PostgreSQL data for reporting.
- LLM-assisted normalization utilities under ``src/llm_hosting``.

Main entry points
-----------------

- ``src/run.py``: starts the Flask app.
- ``src/main.py``: pull/update data orchestration.
- ``src/query_data.py``: reporting queries.
- ``src/load_data.py``: loading records into PostgreSQL.
