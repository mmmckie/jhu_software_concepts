import psycopg
import json
from datetime import datetime

# conn_info = "dbname=grad_data user=postgres password=password host=localhost"
base_conn_info = 'dbname=postgres user=postgres host=localhost'
dbname = 'grad_data'
conn_info = f'dbname={dbname} user=postgres host=localhost'

def create_db_if_not_exists():
    # Connect to default 'postgres' db to perform administrative task
    with psycopg.connect(base_conn_info, autocommit=True) as conn:
        with conn.cursor() as cur:
            # Check if grad_data exists
            cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (dbname,))
            exists = cur.fetchone()
            
            if not exists:
                print(f"Database '{dbname}' not found. Creating it now...")
                cur.execute(f"CREATE DATABASE {dbname}")
            else:
                print(f"Database '{dbname}' already exists.")

def get_max_result_page():
    try:
        with psycopg.connect(conn_info) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT MAX(result_page) FROM admissions;")
                result = cur.fetchone()
                return result[0] if result and result[0] is not None else None
    except Exception:
        return None


def get_existing_urls():
    try:
        with psycopg.connect(conn_info) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT url FROM admissions;")
                return {row[0] for row in cur.fetchall() if row[0]}
    except Exception:
        return set()


def format_date(date_str):
    """Converts 'January 28, 2026' to '2026-01-28' for Postgres."""
    if not date_str:
        return None
    try:
        return datetime.strptime(date_str, "%B %d, %Y").date()
    except ValueError:
        return None

def stream_jsonl_to_postgres(filepath):
    
    create_db_if_not_exists()

    with psycopg.connect(conn_info) as conn:
        with conn.cursor() as cur:
            # 1. Create table with proper numeric types
            # NUMERIC(3, 2) is perfect for GPA (e.g., 4.00)
            
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
                    degree TEXT, -- Set to TEXT as 'PhD'/'MS' aren't numbers
                    llm_generated_program TEXT,
                    llm_generated_university TEXT,
                    result_page INTEGER -- The end of URL (result number)
                );
            """)
            cur.execute("CREATE UNIQUE INDEX IF NOT EXISTS admissions_url_key ON admissions (url);")

            with open(filepath, 'r', encoding='utf-8') as f:
                for line in f:
                    # print(type(line))
                    # print(line.values())
                    # print(line)
                    if not line.strip():
                        continue
                    # try:
                    record = json.loads(line)
                    if '' in record.values():
                        continue
                    # 2. Map JSON keys to the Database columns
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
                        record.get('university'), # + " - " + record.get('program'), # Combined for 'program'
                        record.get('program'),
                        record.get('comments'),
                        format_date(record.get('date added')), # Convert string to Date object
                        record.get('url'),
                        record.get('application status'),
                        record.get('term'),
                        record.get('US/International'),
                        record.get('GPA'),
                        record.get('GRE'),   # Using your specified 'gre' field
                        record.get('GRE V'),
                        record.get('GRE AW'),
                        record.get('degree'),
                        record.get('llm-generated-program'), # From your LLM step
                        record.get('llm-generated-university'), # From your LLM step
                        record.get('url').split('/')[-1]
                    ))
                    # except Exception as e:
                    #     print(f'Exception {e} occured. Data in question:')
                    #     print(line, end = '\n')

            
            conn.commit()
    print("SUCCESS: Database populated")

if __name__ == "__main__":
    stream_jsonl_to_postgres('llm_extend_applicant_data.jsonl')
