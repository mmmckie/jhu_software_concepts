This module implements a data pipeline and web app for GradCafe admissions analysis. It scrapes raw records, cleans and normalizes fields (including LLM-based standardization), loads data into PostgreSQL, and serves summary metrics through a Flask dashboard and API endpoints.

Fresh Install
===============================================================================
1. Install PostgreSQL
2. Install Python 3.12.3
3. $git clone git@github.com:mmmckie/jhu_software_concepts.git
4. $cd jhu_software_concepts/module_5

---------------------------------------------------------------
Method 1: pip

5. $python -m venv .venv
6. $source .venv/bin/activate
7. $pip install -r requirements.txt
8. $pip install -e .
---------------------------------------------------------------
Method 2: uv

5. $uv venv
6. $source .venv/bin/activate
7. $uv pip sync requirements.txt
8. $uv pip install -e .
---------------------------------------------------------------

9. Copy `../.env.example` to `../.env` and set real DB values.
10. (Optional but recommended) create least-privilege DB role:
    `$PGPASSWORD='<postgres_admin_password>' psql -h localhost -p 5432 -U postgres -d postgres -f docs/least_privilege.sql`

    (Shorthand that may work if your local defaults are already configured:)
    `$psql -U postgres -f docs/least_privilege.sql`
11. $python src/run.py

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

===============================================================================
Run Pylint Check:

1. $cd jhu_software_concepts/module_5
2. $pylint src/

===============================================================================
Documentation:

https://mmmckie-jhu-software-concepts.readthedocs.io/en/latest/
