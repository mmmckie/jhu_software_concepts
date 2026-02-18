"""Analytical query layer for admissions reporting metrics."""

# Approach: run focused SQL queries and merge scalar results into one dashboard payload.
import psycopg
from psycopg import sql
from db_config import get_db_conn_info

# Use the same connection string as your loader
conn_info = get_db_conn_info()
MAX_QUERY_LIMIT = 100


def _render_sql(stmt):
    """Render a psycopg SQL composable without requiring a live connection object."""
    class _Ctx:  # Minimal context object for psycopg.sql rendering.
        connection = None

    return stmt.as_string(_Ctx())


def _clamp_limit(limit, minimum=1, maximum=MAX_QUERY_LIMIT):
    """Clamp a requested row limit to a safe bounded range."""
    value = int(limit)
    return max(minimum, min(value, maximum))


def _query_to_composable(query):
    """Convert raw SQL text or composable SQL into a composable object."""
    cleaned = str(query).strip().rstrip(';')
    return sql.SQL(cleaned)


def _compose_limited_query(query, limit):
    """Build a LIMIT-capped SQL statement around an arbitrary base query."""
    base_query = _query_to_composable(query)
    safe_limit = _clamp_limit(limit)
    stmt = sql.SQL(
        "SELECT * FROM ({base_query}) AS analysis_query LIMIT {limit_value}"
    ).format(
        base_query=base_query,
        limit_value=sql.SQL(str(safe_limit)),
    )
    return stmt

def _query_scalar(query):
    """Return the first scalar value from a SQL query."""
    return execute_query(query)[0][0]


def _build_overview_metrics():
    """Build top-level overview metrics used by the dashboard."""
    total_records = _query_scalar("SELECT COUNT(*) FROM admissions;")
    fall_2026_applicants = _query_scalar(
        """
        SELECT COUNT(*) FROM admissions
        WHERE term = 'Fall 2026';
        """
    )
    internationals = _query_scalar(
        """
        SELECT COUNT(*) FROM admissions
        WHERE us_or_international = 'International';
        """
    )
    international_percentage = (
        round((internationals / total_records) * 100, 2) if total_records else 0.0
    )
    return {
        'total_records': total_records,
        'fall_2026_applicants': fall_2026_applicants,
        'international_percentage': international_percentage,
    }


def _build_academic_metrics():
    """Build average-score and acceptance-rate metrics."""
    gpa, gre, gre_v, gre_aw = execute_query(
        """
        SELECT
            ROUND(AVG(gpa)::numeric, 2) AS avg_gpa,
            ROUND(AVG(gre)::numeric, 1) AS avg_gre_quant,
            ROUND(AVG(gre_v)::numeric, 1) AS avg_gre_verbal,
            ROUND(AVG(gre_aw)::numeric, 2) AS avg_gre_aw
        FROM admissions
        WHERE
            (gpa BETWEEN 0.1 AND 5.0)
            AND (gre BETWEEN 130 AND 170)
            AND (gre_v BETWEEN 130 AND 170)
            AND (gre_aw BETWEEN 0.0 AND 6.0);
        """
    )[0]
    american_fall_2026_gpa = _query_scalar(
        """
        SELECT
            ROUND(AVG(gpa)::numeric, 2) AS avg_gpa
        FROM admissions
        WHERE
            (gpa BETWEEN 0.1 AND 5.0)
            AND (us_or_international = 'American')
            AND (term = 'Fall 2026');
        """
    )
    fall_2025_acceptance_rate = _query_scalar(
        """
        SELECT
            ROUND(
                (COUNT(*) FILTER (WHERE status = 'Accepted')::numeric /
                COUNT(*) * 100),
                2
            ) as acceptance_percentage
        FROM admissions
        WHERE term = 'Fall 2025';
        """
    )
    fall_2026_acceptance_gpa = _query_scalar(
        """
        SELECT
            ROUND(AVG(gpa)::numeric, 2) AS avg_gpa
        FROM admissions
        WHERE
            (term = 'Fall 2026')
            AND (status = 'Accepted');
        """
    )
    return {
        'average_metrics': {
            'gpa': gpa,
            'gre': gre,
            'gre_v': gre_v,
            'gre_aw': gre_aw,
        },
        'american_fall_2026_gpa': american_fall_2026_gpa,
        'fall_2025_acceptance_rate': fall_2025_acceptance_rate,
        'fall_2026_acceptance_gpa': fall_2026_acceptance_gpa,
    }


def _build_program_metrics():
    """Build targeted program/university query metrics."""
    jhu_cs_masters = _query_scalar(
        """
        SELECT COUNT(*)
        FROM admissions
        WHERE (
            llm_generated_university ILIKE '%john%hopkin%'
            OR university ILIKE '%jhu%'
            OR university ILIKE '%john%hopkin%'
        )
        AND (
            llm_generated_program ILIKE '%comp%sci%'
            OR program ILIKE '%comp%sci%'
            OR program = 'CS'
        )
        AND (degree = 'Masters');
        """
    )
    ivy_2026_compsci_phds = _query_scalar(
        """
        SELECT COUNT(*)
        FROM admissions
        WHERE (
            llm_generated_university = 'Massachusetts Institute of Technology'
            OR university ILIKE '%mass%institute%tech'
            OR university = 'MIT'
            OR llm_generated_university = 'Stanford University'
            OR university ILIKE '%stanford%'
            OR university = 'SU'
            OR llm_generated_university = 'Georgetown University'
            OR university ILIKE '%georgetown%'
            OR llm_generated_university = 'Carnegie Mellon University'
            OR university ILIKE '%carnegie%mellon%'
            OR university ILIKE '%carnegie%melon%'
            OR university = 'CMU'
        )
        AND (date_added BETWEEN '2026-01-01' AND '2026-12-31')
        AND (
            llm_generated_program ILIKE '%comp%sci%'
            OR program ILIKE '%comp%sci%'
            OR program = 'CS'
        )
        AND (degree = 'PhD');
        """
    )
    ivy_2026_compsci_phds_llm_fields = _query_scalar(
        """
        SELECT COUNT(*)
        FROM admissions
        WHERE (
            llm_generated_university = 'Massachusetts Institute of Technology'
            OR llm_generated_university = 'Stanford University'
            OR llm_generated_university = 'Georgetown University'
            OR llm_generated_university = 'Carnegie Mellon University'
        )
        AND (date_added BETWEEN '2026-01-01' AND '2026-12-31')
        AND (llm_generated_program ILIKE '%comp%sci%')
        AND (degree = 'PhD');
        """
    )
    ivy_2026_compsci_phds_raw_fields = _query_scalar(
        """
        SELECT COUNT(*)
        FROM admissions
        WHERE (
            university ILIKE '%mass%institute%tech'
            OR university = 'MIT'
            OR university ILIKE '%stanford%'
            OR university = 'SU'
            OR university ILIKE '%georgetown%'
            OR university ILIKE '%carnegie%mellon%'
            OR university ILIKE '%carnegie%melon%'
            OR university = 'CMU'
        )
        AND (date_added BETWEEN '2026-01-01' AND '2026-12-31')
        AND (
            program ILIKE '%comp%sci%'
            OR program = 'CS'
        )
        AND (degree = 'PhD');
        """
    )
    return {
        'jhu_cs_masters': jhu_cs_masters,
        'ivy_2026_compsci_phds': ivy_2026_compsci_phds,
        'ivy_2026_compsci_phds_llm_fields': ivy_2026_compsci_phds_llm_fields,
        'ivy_2026_compsci_phds_raw_fields': ivy_2026_compsci_phds_raw_fields,
    }


def _build_additional_metrics():
    """Build term comparison and GPA-reporting acceptance metrics."""
    fall_2025_applicants, spring_2025_applicants = execute_query(
        """
        SELECT
            COUNT(*) FILTER (WHERE term = 'Fall 2025') as fall_count,
            COUNT(*) FILTER (WHERE term = 'Spring 2025') as spring_count
        FROM admissions;
        """
    )[0]
    masters_acceptance = execute_query(
        """
        SELECT
            CASE
                WHEN gpa IS NOT NULL THEN 'Reported GPA'
                ELSE 'No GPA'
            END AS gpa_status,
            COUNT(*) as total_apps,
            ROUND(
                (COUNT(*) FILTER (WHERE status = 'Accepted')::numeric / COUNT(*) * 100),
                2
            ) as acceptance_rate
        FROM admissions
        WHERE degree = 'Masters'
        AND us_or_international = 'American'
        GROUP BY gpa_status;
        """
    )
    phd_acceptance = execute_query(
        """
        SELECT
            CASE
                WHEN gpa IS NOT NULL THEN 'Reported GPA'
                ELSE 'No GPA'
            END AS gpa_status,
            COUNT(*) as total_apps,
            ROUND(
                (COUNT(*) FILTER (WHERE status = 'Accepted')::numeric / COUNT(*) * 100),
                2
            ) as acceptance_rate
        FROM admissions
        WHERE degree = 'PhD'
        AND us_or_international = 'American'
        GROUP BY gpa_status;
        """
    )
    masters_map = {row[0]: row[-1] for row in masters_acceptance}
    phd_map = {row[0]: row[-1] for row in phd_acceptance}
    return {
        'fall_2025_applicants': fall_2025_applicants,
        'spring_2025_applicants': spring_2025_applicants,
        'masters_acceptance': {
            'with_gpa': masters_map.get('Reported GPA'),
            'no_gpa': masters_map.get('No GPA'),
        },
        'phd_acceptance': {
            'with_gpa': phd_map.get('Reported GPA'),
            'no_gpa': phd_map.get('No GPA'),
        },
    }


def run_analysis():
    """Compute all dashboard metrics from the admissions table."""
    analysis = {}
    analysis.update(_build_overview_metrics())
    analysis.update(_build_academic_metrics())
    analysis.update(_build_program_metrics())
    analysis.update(_build_additional_metrics())
    return analysis


def execute_query(query, params=None, limit=MAX_QUERY_LIMIT):
    """Execute a SQL query and return all result rows.

    :param query: SQL query text to execute.
    :type query: str | psycopg.sql.Composable
    :param params: Optional SQL parameter values for placeholders in ``query``.
    :type params: list | tuple | None
    :param limit: Maximum number of rows to return, clamped to [1, 100].
    :type limit: int
    :returns: List of row tuples fetched from PostgreSQL.
    :rtype: list[tuple]
    :raises RuntimeError: Wrapped database exception with contextual message.
    """
    try:
        connection = psycopg.connect(conn_info)
        with connection.cursor() as cur:  # pylint: disable=no-member
            stmt = _compose_limited_query(query, limit)
            exec_params = params if params else None
            cur.execute(_render_sql(stmt), exec_params)
            return cur.fetchall()

    except Exception as e:
        raise RuntimeError(f'Database query failed: {e}') from e


if __name__ == '__main__':
    # Collect and print all analysis results
    analysis_results = run_analysis()
    print(f"There are {analysis_results['total_records']} entries")
    print()
    print(f"There were {analysis_results['fall_2026_applicants']} Fall 2026 applicant entries.")
    print()
    print(
        f"There were {analysis_results['international_percentage']:0.2f}% "
        "International applicant entries."
    )
    print()
    avg = analysis_results['average_metrics']
    print(f"Average metrics - GPA: {avg['gpa']} | GRE: {avg['gre']} | GRE V: {avg['gre_v']} | "
          f"GRE AW: {avg['gre_aw']}")
    print()
    print(f"Fall 2026 American Applicant Avg GPA: {analysis_results['american_fall_2026_gpa']}")
    print()
    print(f"Fall 2025 Acceptance Rate: {analysis_results['fall_2025_acceptance_rate']}%")
    print()
    print(f"Avg GPA of Fall 2026 Acceptances: {analysis_results['fall_2026_acceptance_gpa']}")
    print()
    print(f"Number of JHU Master's CS applicants: {analysis_results['jhu_cs_masters']}")
    print()
    print(
        "2026 PhD Acceptances from Georgetown, MIT, Stanford, and Carnegie Mellon: "
        f"{analysis_results['ivy_2026_compsci_phds']}"
    )
    print(
        "Same info relying on LLM generated fields only: "
        f"{analysis_results['ivy_2026_compsci_phds_llm_fields']}"
    )
    print(
        "Same info relying on raw fields only: "
        f"{analysis_results['ivy_2026_compsci_phds_raw_fields']}"
    )
    print()
    print(f"Fall 2025 Applicants: {analysis_results['fall_2025_applicants']}")
    print(f"Spring 2025 Applicants: {analysis_results['spring_2025_applicants']}")
    print()
    print("Master's program acceptance rates with/without reported GPA...")
    print(
        f"With GPA: {analysis_results['masters_acceptance']['with_gpa']}% | "
        f"No GPA: {analysis_results['masters_acceptance']['no_gpa']}%"
    )
    print()
    print("PhD program acceptance rates with/without reported GPA...")
    print(
        f"With GPA: {analysis_results['phd_acceptance']['with_gpa']}% | "
        f"No GPA: {analysis_results['phd_acceptance']['no_gpa']}%"
    )
