This module implements a data pipeline and web app for GradCafe admissions analysis. It scrapes raw records, cleans and normalizes fields (including LLM-based standardization), loads data into PostgreSQL, and serves summary metrics through a Flask dashboard and API endpoints.

Fresh Install

Method 1: pip

1. Install Python 3.12.3 and PostgreSQL.
2. `cd jhu_software_concepts/module_5`
3. `python -m venv .venv`
4. `source .venv/bin/activate`
5. `pip install -r requirements.txt`
6. `pip install -e .`
7. Copy `../.env.example` to `../.env` and set real DB values.

Method 2: uv

1. Install Python 3.12.3, PostgreSQL, and `uv`.
2. `cd jhu_software_concepts/module_5`
3. `uv venv`
4. `source .venv/bin/activate`
5. `uv pip sync requirements.txt`
6. `uv pip install -e .`
7. Copy `../.env.example` to `../.env` and set real DB values.

Steps to run analysis webpage on localhost:

(1) Install PostgreSQL
(2) Install Python 3.12.3
(3) $git clone git@github.com:mmmckie/jhu_software_concepts.git
(4) Ensure current working directory is jhu_software_concepts/module_5
(5) $pip install -r requirements.txt
(6) $pip install -e .
(7) Copy `../.env.example` to `../.env` and set real DB values
(8) (Optional but recommended) create least-privilege DB role:
    `$psql -U postgres -f docs/least_privilege.sql`
(9) $python src/run.py

Environment variables used by the app:

- `DB_HOST`
- `DB_PORT`
- `DB_NAME`
- `DB_USER`
- `DB_PASSWORD`
- `DB_ADMIN_HOST` (optional)
- `DB_ADMIN_PORT` (optional)
- `DB_ADMIN_NAME` (optional)
- `DB_ADMIN_USER` (optional)
- `DB_ADMIN_PASSWORD` (optional)

Least-privilege guidance:

- Use a dedicated app role (for example `grad_app`)
- Do not grant `SUPERUSER`, `CREATEDB`, `CREATEROLE`, `ALTER`, or `DROP`
- Grant only what the app needs on `public.admissions`:
  - `SELECT`, `INSERT`, `UPDATE`
  - sequence usage on `public.admissions_p_id_seq`

Documentation:

https://mmmckie-jhu-software-concepts.readthedocs.io/en/latest/
