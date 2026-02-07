import psycopg

# Use the same connection string as your loader
conn_info = 'dbname=grad_data user=postgres host=localhost'

def run_analysis():
    '''
    Executes several queries on database created using TheGradCafe applicant
    data and returns dict of all resulting metrics.
    '''
    # dict to store all following metrics
    results = {}

    # TOTAL NUMBER OF RECORDS COLLECTED
    query = """
        SELECT COUNT(*) FROM admissions;
        """
    total_records = execute_query(query)[0][0]
    results['total_records'] = total_records

    # NUMBER OF RECORDS FOR FALL 2026 TERM
    query = """
        SELECT COUNT(*) FROM admissions
        WHERE term = 'Fall 2026';
        """
    fall_2026_applicants = execute_query(query)[0][0]
    results['fall_2026_applicants'] = fall_2026_applicants

    # PERCENTAGE OF ENTRIES FROM INTERNATIONAL STUDENTS
    query = """
        SELECT COUNT(*) FROM admissions
        WHERE us_or_international = 'International';
        """
    internationals = execute_query(query)[0][0]
    if total_records:
        results['international_percentage'] = round((internationals / total_records) * 100, 2)
    else:
        results['international_percentage'] = 0.0

    # AVERAGE GPA, GRE, GRE V, GRE AW
    query = """
        SELECT 
            ROUND(AVG(gpa)::numeric, 2) AS avg_gpa,
            ROUND(AVG(gre)::numeric, 1) AS avg_gre_quant,
            ROUND(AVG(gre_v)::numeric, 1) AS avg_gre_verbal,
            ROUND(AVG(gre_aw)::numeric, 2) AS avg_gre_aw
        FROM admissions
        WHERE 
            (gpa BETWEEN 0.1 AND 5.0) -- Excludes 0.0 and outliers (e.g., 5.0 or 10.0)
            AND (gre BETWEEN 130 AND 170)
            AND (gre_v BETWEEN 130 AND 170)
            AND (gre_aw BETWEEN 0.0 AND 6.0);
        """

    gpa_gre_scores = execute_query(query)[0]
    gpa, gre, gre_v, gre_aw = gpa_gre_scores
    results['average_metrics'] = {
        'gpa': gpa,
        'gre': gre,
        'gre_v': gre_v,
        'gre_aw': gre_aw,
    }

    # AMERICAN STUDENT AVG GPA FOR FALL 2026 TERM
    query = """
        SELECT 
            ROUND(AVG(gpa)::numeric, 2) AS avg_gpa
        FROM admissions
        WHERE 
            (gpa BETWEEN 0.1 AND 5.0)
            AND (us_or_international = 'American')
            AND (term = 'Fall 2026');
        """

    american_fall_2026_gpa = execute_query(query)[0][0]
    results['american_fall_2026_gpa'] = american_fall_2026_gpa

    # PERCENT ACCEPTANCES FOR FALL 2025
    query = """
        SELECT 
            ROUND(
                (COUNT(*) FILTER (WHERE status = 'Accepted')::numeric / 
                COUNT(*) * 100), 
                2
            ) as acceptance_percentage
        FROM admissions
        WHERE term = 'Fall 2025';
        """

    fall_2025_acceptance_rate = execute_query(query)[0][0]
    results['fall_2025_acceptance_rate'] = fall_2025_acceptance_rate

    # AVERAGE GPA OF FALL 2026 ACCEPTANCES
    query = """
        SELECT 
            ROUND(AVG(gpa)::numeric, 2) AS avg_gpa
        FROM admissions
        WHERE
            (term = 'Fall 2026')
            AND (status = 'Accepted');
        """

    fall_2026_acceptance_gpa = execute_query(query)[0][0]
    results['fall_2026_acceptance_gpa'] = fall_2026_acceptance_gpa

    # NUMBER OF JHU MASTER'S COMPUTER SCIENCE APPLICATIONS
    query = """
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
    
    jhu_cs_masters = execute_query(query)[0][0]
    results['jhu_cs_masters'] = jhu_cs_masters

    # 2026 PHD COMPUTER SCIENCE ACCEPTANCES FROM GEORGETOWN, MIT, STANFORD, CARNEGIE MELLON
    query = """
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
    
    ivy_2026_compsci_phds = execute_query(query)[0][0]
    results['ivy_2026_compsci_phds'] = ivy_2026_compsci_phds

    # SAME 2026 PHD COMPSCI ACCEPTANCES, RELYING ON ONLY LLM VS RAW DATA

    query_llm_fields = """
        SELECT COUNT(*) 
        FROM admissions
        WHERE (
            llm_generated_university = 'Massachusetts Institute of Technology'
            OR llm_generated_university = 'Stanford University'
            OR llm_generated_university = 'Georgetown University'
            OR llm_generated_university = 'Carnegie Mellon University'

        )
        AND (date_added BETWEEN '2026-01-01' AND '2026-12-31')
        AND (
            llm_generated_program ILIKE '%comp%sci%' 
        )
        AND (degree = 'PhD');
        """
    
    query_raw_fields = """
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

    ivy_2026_compsci_phds_llm_fields = execute_query(query_llm_fields)[0][0]
    ivy_2026_compsci_phds_raw_fields = execute_query(query_raw_fields)[0][0]

    results['ivy_2026_compsci_phds_llm_fields'] = ivy_2026_compsci_phds_llm_fields
    results['ivy_2026_compsci_phds_raw_fields'] = ivy_2026_compsci_phds_raw_fields

    ### EXTRA QUESTION 1)
    # How many more applicants applied for a Fall 2025 start term vs a
    # Spring 2025 start term?
    query = """
        SELECT 
            COUNT(*) FILTER (WHERE term = 'Fall 2025') as fall_count,
            COUNT(*) FILTER (WHERE term = 'Spring 2025') as spring_count
        FROM admissions;
        """
    fall_2025_applicants, spring_2025_applicants = execute_query(query)[0]
    results['fall_2025_applicants'] = fall_2025_applicants
    results['spring_2025_applicants'] = spring_2025_applicants

    ### EXTRA QUESTION 2)
    # What is the average acceptance rate of Master's programs vs PhD programs
    # for American applicants who do and don't report their GPA?

    # Hypothesis: Low/embarrassing GPAs are less likely to be self-reported; the
    # acceptance rate of each will rise if there is a self-reported GPA

    query_masters = """
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
    
    query_phd = """
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
    
    masters_acceptance = execute_query(query_masters)
    phd_acceptance = execute_query(query_phd)

    masters_map = {row[0]: row[-1] for row in masters_acceptance}
    phd_map = {row[0]: row[-1] for row in phd_acceptance}

    results['masters_acceptance'] = {
        'with_gpa': masters_map.get('Reported GPA'),
        'no_gpa': masters_map.get('No GPA'),
    }
    results['phd_acceptance'] = {
        'with_gpa': phd_map.get('Reported GPA'),
        'no_gpa': phd_map.get('No GPA'),
    }
    return results


def execute_query(query):
    '''Executes a SQL query on a postgreSQL database and returns the result.'''
    
    try:
        connection = psycopg.connect(conn_info)
        with connection.cursor() as cur:
            cur.execute(query)
            return cur.fetchall()
            
    except Exception as e:
        raise RuntimeError(f'Database query failed: {e}') from e

if __name__ == '__main__':
    # Execute all queries and collect results
    results = run_analysis()

    # Print the analysis results to console
    print(f'There are {results['total_records']} entries')
    print()
    print(f'There were {results['fall_2026_applicants']} Fall 2026 applicant entries.')
    print()
    print(f'There were {results['international_percentage']: 0.2f}% International applicant entries.')
    print()
    avg = results['average_metrics']
    print(
        'Average metrics - GPA: {gpa} | GRE: {gre} | GRE V: {gre_v} | GRE AW: {gre_aw}'.format(
            **avg
        )
    )
    print()
    print(f'Fall 2026 American Applicant Avg GPA: {results['american_fall_2026_gpa']}')
    print()
    print(f'Fall 2025 Acceptance Rate: {results['fall_2025_acceptance_rate']}%')
    print()
    print(f'Avg GPA of Fall 2026 Acceptances: {results['fall_2026_acceptance_gpa']}')
    print()
    print(f'Number of JHU Master\'s CS applicants: {results['jhu_cs_masters']}')
    print()
    print(
        '2026 PhD Acceptances from Georgetown, MIT, Stanford, and Carnegie Mellon: '
        f'{results['ivy_2026_compsci_phds']}'
    )
    print(
        'Same info relying on LLM generated fields only: '
        f'{results['ivy_2026_compsci_phds_llm_fields']}'
    )
    print(
        'Same info relying on raw fields only: '
        f'{results['ivy_2026_compsci_phds_raw_fields']}'
    )
    print()
    print(f'Fall 2025 Applicants: {results['fall_2025_applicants']}')
    print(f'Spring 2025 Applicants: {results['spring_2025_applicants']}')
    print()
    print('Master\'s program acceptance rates with/without reported GPA...')
    print(
        f'With GPA: {results['masters_acceptance']['with_gpa']}% | '
        f'No GPA: {results['masters_acceptance']['no_gpa']}%'
    )
    print()
    print('PhD program acceptance rates with/without reported GPA...')
    print(
        f'With GPA: {results['phd_acceptance']['with_gpa']}% | '
        f'No GPA: {results['phd_acceptance']['no_gpa']}%'
    )
