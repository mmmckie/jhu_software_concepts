"""PostgreSQL load helpers for admissions JSONL data."""

# Keep connection settings centralized so create/query/load paths share the same DB target.
import os
import json
import sys
from pathlib import Path
from datetime import datetime
import psycopg
from psycopg import sql
from db_config import get_admin_conn_info, get_db_conn_info, get_db_name

base_conn_info = get_admin_conn_info()
DBNAME = get_db_name()
conn_info = get_db_conn_info()
MAX_QUERY_LIMIT = 100


def _clamp_limit(limit, minimum=1, maximum=MAX_QUERY_LIMIT):
    """Clamp a requested row limit to a safe bounded range."""
    value = int(limit)
    return max(minimum, min(value, maximum))

def create_db_if_not_exists():
    """Create the ``grad_data`` database when unmanaged local defaults are used.

    If ``DATABASE_URL`` is explicitly set, provisioning is assumed to be
    managed externally and this function exits immediately.

    :returns: ``None``.
    :rtype: None
    """
    # When DATABASE_URL is explicitly configured, assume DB provisioning is external.
    if os.getenv('DATABASE_URL'):
        return
    # Connect to default 'postgres' db to perform administrative task
    with psycopg.connect(base_conn_info, autocommit=True) as conn:
        with conn.cursor() as cur:
            # Check if grad_data exists
            cur.execute('SELECT 1 FROM pg_database WHERE datname = %s', (DBNAME,))
            exists = cur.fetchone()

            if not exists:
                print(f'Database {DBNAME} not found. Creating it now...')
                stmt = sql.SQL('CREATE DATABASE {db_name}').format(
                    db_name=sql.Identifier(DBNAME)
                )
                cur.execute(stmt)
            else:
                print(f'Database {DBNAME} already exists.')

def get_max_result_page():
    """Fetch the highest ingested GradCafe result-page number.

    :returns: Maximum ``result_page`` value, or ``None`` if unavailable.
    :rtype: int | None
    """
    try:
        with psycopg.connect(conn_info) as conn:
            with conn.cursor() as cur:
                cur.execute('SELECT MAX(result_page) FROM admissions LIMIT %s;', (1,))
                result = cur.fetchone()
                return result[0] if result and result[0] is not None else None
    except (psycopg.Error, RuntimeError):
        # Absence of table/DB is treated as "no known max page" for first run.
        return None


def get_existing_urls():
    """Fetch all existing admissions URLs currently stored in PostgreSQL.

    :returns: Set of unique URL strings, or empty set on connection/query error.
    :rtype: set[str]
    """
    try:
        limit = _clamp_limit(MAX_QUERY_LIMIT)
        offset = 0
        urls = set()
        with psycopg.connect(conn_info) as conn:
            with conn.cursor() as cur:
                while True:
                    cur.execute(
                        '''
                        SELECT url
                        FROM admissions
                        WHERE url IS NOT NULL
                        ORDER BY url
                        LIMIT %s OFFSET %s;
                        ''',
                        (limit, offset),
                    )
                    rows = cur.fetchall()
                    if not rows:
                        break
                    urls.update(row[0] for row in rows if row[0])
                    if len(rows) < limit:
                        break
                    offset += limit
                return urls
    except (psycopg.Error, RuntimeError):
        return set()


def format_date(date_str):
    """Convert date text to a ``date`` object compatible with PostgreSQL.

    :param date_str: Date string in ``'%B %d, %Y'`` format.
    :type date_str: str | None
    :returns: Parsed date or ``None`` when missing/invalid.
    :rtype: datetime.date | None
    """
    if not date_str:
        return None
    try:
        return datetime.strptime(date_str, '%B %d, %Y').date()
    except ValueError:
        return None


def _admissions_table_exists(cur):
    """Return whether ``public.admissions`` is present in the target DB."""
    cur.execute("SELECT to_regclass('public.admissions');")
    row = cur.fetchone()
    return bool(row and row[0])


def _provision_admissions_schema():
    """Create admissions table/index with admin credentials when missing.

    This keeps app-role ingestion least-privilege: regular writes do not need
    CREATE rights on schema ``public``.
    """
    if os.getenv('DATABASE_URL'):
        raise RuntimeError(
            'admissions table is missing and DATABASE_URL is explicitly set; '
            'provision schema externally or provide DB_ADMIN_* credentials.'
        )

    app_user = os.getenv('DB_USER')
    with psycopg.connect(base_conn_info) as admin_conn:
        with admin_conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS admissions (
                    p_id SERIAL PRIMARY KEY,
                    university TEXT,
                    program TEXT,
                    comments TEXT,
                    date_added DATE,
                    url TEXT,
                    status TEXT,
                    term TEXT,
                    us_or_international TEXT,
                    gpa DOUBLE PRECISION,
                    gre DOUBLE PRECISION,
                    gre_v DOUBLE PRECISION,
                    gre_aw DOUBLE PRECISION,
                    degree TEXT,
                    llm_generated_program TEXT,
                    llm_generated_university TEXT,
                    result_page INTEGER
                );
            """)
            cur.execute('CREATE UNIQUE INDEX IF NOT EXISTS admissions_url_key ON admissions (url);')

            if app_user:
                cur.execute(
                    sql.SQL('GRANT USAGE ON SCHEMA public TO {role}').format(
                        role=sql.Identifier(app_user)
                    )
                )
                cur.execute(
                    sql.SQL(
                        'GRANT SELECT, INSERT, UPDATE ON TABLE public.admissions TO {role}'
                    ).format(role=sql.Identifier(app_user))
                )
                cur.execute(
                    sql.SQL(
                        'GRANT USAGE, SELECT ON SEQUENCE public.admissions_p_id_seq TO {role}'
                    ).format(role=sql.Identifier(app_user))
                )
        admin_conn.commit()


def stream_jsonl_to_postgres(filepath):
    """Stream JSONL records into PostgreSQL admissions table.

    The function ensures the admissions schema exists (using admin credentials
    only when missing), inserts rows with ``ON CONFLICT (url) DO NOTHING``, and
    commits once all valid records are processed.

    :param filepath: Path to line-delimited JSON records.
    :type filepath: str
    :returns: ``None``.
    :rtype: None
    :raises Exception: Propagates unexpected filesystem or database errors.
    """
    create_db_if_not_exists()

    with psycopg.connect(conn_info) as conn:
        with conn.cursor() as cur:
            if not _admissions_table_exists(cur):
                _provision_admissions_schema()

            with open(filepath, 'r', encoding='utf-8') as f:
                for line in f:

                    # Ensure record is not empty and has no missing fields
                    if not line.strip():
                        continue
                    record = json.loads(line)
                    # Reject partial rows to keep downstream analytics assumptions valid.
                    if '' in record.values():
                        continue

                    # Map JSON keys to the Database columns
                    cur.execute("""
                        INSERT INTO admissions (
                            university, program, comments, date_added, url,
                            status, term, us_or_international, gpa, gre, gre_v, 
                            gre_aw, degree, llm_generated_program, 
                            llm_generated_university, result_page
                        )
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (url) DO NOTHING
                    """, (
                        record.get('university'),
                        record.get('program'),
                        record.get('comments'),
                        format_date(record.get('date added')), # Convert string to Date object
                        record.get('url'),
                        record.get('application status'),
                        record.get('term'),
                        record.get('US/International'),
                        record.get('GPA'),
                        record.get('GRE'),
                        record.get('GRE V'),
                        record.get('GRE AW'),
                        record.get('degree'),
                        record.get('llm-generated-program'), # From LLM step
                        record.get('llm-generated-university'), # From LLM step
                        # Store numeric suffix once so incremental scraping can resume quickly.
                        record.get('url').split('/')[-1]
                    ))


            conn.commit()
    print('SUCCESS: Database populated')

if __name__ == '__main__':
    DEFUALT_DATA_PATH = 'llm_extend_applicant_data.jsonl'
    script_dir = Path(__file__).resolve().parent
    default_path = Path(DEFUALT_DATA_PATH)
    fallback_path = script_dir / DEFUALT_DATA_PATH
    cli_path = next(
        (
            arg
            for arg in sys.argv[1:]
            if not arg.startswith('-') and Path(arg).exists()
        ),
        None,
    )
    input_path = (
        Path(cli_path)
        if cli_path is not None
        else (default_path if default_path.exists() else fallback_path)
    )
    stream_jsonl_to_postgres(str(input_path))
