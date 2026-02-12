Architecture
============

The module is organized into three primary layers plus an optional LLM service.

Web layer
---------

- Entry point: ``src/run.py``
- App factory: ``src/board/__init__.py``
- Route handlers: ``src/board/pages.py``
- Templates/static assets:
  ``src/board/templates/`` and ``src/board/static/``

Responsibilities:

- Render analysis UI (``/`` and ``/analysis``)
- Handle pull/update actions for browser and API endpoints
- Enforce busy-state behavior during pull operations

ETL layer
---------

- Scraping: ``src/scrape.py``
- Cleaning/normalization prep: ``src/clean.py``
- Orchestration: ``src/main.py``
- Optional LLM field standardization: ``src/llm_hosting/app.py``

Responsibilities:

- Pull raw records from GradCafe pages
- Normalize text/data fields and optional values
- Produce JSON/JSONL artifacts
- Incrementally append and ingest newly discovered records

Database layer
--------------

- Load/DDL and inserts: ``src/load_data.py``
- Analytics queries: ``src/query_data.py``

Responsibilities:

- Ensure admissions table/index exist
- Insert line-delimited JSON records into PostgreSQL
- Compute analysis metrics consumed by the dashboard

Data flow summary
-----------------

1. ``Pull Data`` triggers ``update_new_records()``.
2. Scraped records are cleaned and optionally LLM-standardized.
3. New records are appended to canonical JSON/JSONL files in ``src/``.
4. New JSONL is loaded into PostgreSQL.
5. ``Update Analysis`` recalculates dashboard metrics from DB queries.
