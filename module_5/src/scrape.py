"""GradCafe scraping helpers for survey and result-page extraction."""

# Approach: collect table rows first, then hydrate each row with detailed result-page fields.
from concurrent.futures import ThreadPoolExecutor
import time
from urllib import error, request
from urllib.request import urlopen

from bs4 import BeautifulSoup


BASE_URL = 'https://www.thegradcafe.com'

# 21 records per page should provide ~40k results
NUM_PAGES_OF_DATA = 2000

# MAX_WORKERS = 10 is a safe "polite" starting point.
# Increase to 20 or 30 if the server handles it well.
MAX_WORKERS = 10

# Anything restricted by robots.txt
DISALLOWED_PAGES = ['/cgi-bin/',
                    '/index-ad-test.php']

# This header makes the scraper look like a standard Chrome browser
HEADERS = {
'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) \
AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
}

RESULT_FIELD_MAP = {
    0: 'university',
    1: 'program',
    2: 'degree',
    3: 'US/International',
    4: 'application status',
    5: 'application status date',
    6: 'GPA',
    8: 'comments',
}


def _is_restricted_path(url):
    """Check whether a URL path is disallowed by configured robots rules.

    :param url: Absolute URL to validate.
    :type url: str
    :returns: ``True`` when the URL contains a disallowed path prefix.
    :rtype: bool
    """
    for restricted_path in DISALLOWED_PAGES:
        if restricted_path in url:
            return True
    return False


def _fetch_table_page(page_num):
    """
    Fetch and parse a single ``/survey`` page.

    :param page_num: Survey page number to request.
    :type page_num: int
    :returns: Parsed rows from the table, grouped by record.
    :rtype: list[list[str]]
    """

    url = f"{BASE_URL}/survey/?page={page_num}"
    if _is_restricted_path(url):
        return []

    try:
        # Create a Request object with the headers
        req = request.Request(url, headers=HEADERS)
        # Use a timeout so the script doesn't hang forever
        with urlopen(req, timeout=10) as response:
            # Create soup object from response bytes
            content = response.read()
            soup = BeautifulSoup(content, 'html.parser')
        table = soup.find('table')

        # If nothing is found, return
        if not table:
            return []

        # Get all rows after skipping the header row
        rows = table.find_all('tr')[1:]

        # Parse rows and combine the data from rows that are part of the same record
        parsed_data = []
        tmp_row = []
        for row in rows:
            # A <tr> tag with no attrs indicates the first row of a new record
            if len(row.attrs) == 0:
                # If tmp_row contains data, store it in parsed_data then clear it
                # It is empty here when the very first row is being processed
                if tmp_row:
                    parsed_data.append(tmp_row)

                tmp_row = []

            # Extract the information from the columns in each row
            cells = [col.get_text() for col in row.find_all('td')]

            # Find the link to the corresponding /result/{result_number} path
            # And insert it at index 0
            link = row.find('a')
            if link:
                link = link.attrs['href']
                tmp_row.insert(0, link)

            # Add all gathered information in this row to tmp_row
            tmp_row.extend(cells)

        # Make sure the very last row of data is added to parsed_data
        if tmp_row:
            parsed_data.append(tmp_row)

        return parsed_data

    except error.HTTPError as e:
        print(f"HTTP Error {e.code} on page {page_num}")
        return []
    except (error.URLError, TimeoutError, ValueError, AttributeError, RuntimeError) as e:
        print(f"Error on page {page_num}: {e}")
        return []


def _extract_result_num(url):
    """Extract integer result id from a result URL.

    :param url: URL containing a trailing result identifier segment.
    :type url: str
    :returns: Parsed result id or ``None`` when invalid.
    :rtype: int | None
    """
    try:
        return int(url.rstrip('/').split('/')[-1])
    except (ValueError, AttributeError):
        return None


def _fetch_result_page(url, payload):
    """Fetch one result page and populate a payload dictionary.

    :param url: Absolute result page URL.
    :type url: str
    :param payload: Existing payload map seeded from survey-table fields.
    :type payload: dict[str, str]
    :returns: Updated payload, or empty dict on failure.
    :rtype: dict[str, str]
    """

    # Check for restricted URLs from robots.txt
    if _is_restricted_path(url):
        return {}

    # Getting page number in case of error to print the specific page
    page_num = url.split('/')[-1]

    try:
        # Create a Request object with the headers
        req = request.Request(url, headers=HEADERS)
        # Use a timeout so the script doesn't hang forever
        with urlopen(req, timeout=10) as response:
            # Create soup object from response bytes
            content = response.read()
            soup = BeautifulSoup(content, 'html.parser')

        # Get all the data fields on the page
        entries = soup.find('dl').find_all('div')

        # Return if nothing found
        if not entries:
            return {}

        # Parse the entries and store raw data in the payload dict, then return
        payload['url'] = url
        for i, entry in enumerate(entries):
            field_name = RESULT_FIELD_MAP.get(i)
            if field_name is not None:
                # Check that the field has text content to avoid errors.
                field_contents = entry.find('dd')
                if field_contents:
                    payload[field_name] = field_contents.get_text()
                continue

            if i == 7: # The GRE scores have a slightly different format
                field_contents = list(entry.find_all('li'))
                # Quant/Verbal/AW values are nested under `<li><span>..</span><b>..</b>`.
                spans = [e.find('span').next_sibling.next_sibling for e in field_contents]
                field_contents = [s.get_text() for s in spans]
                payload['GRE'] = field_contents[0]
                payload['GRE V'] = field_contents[1]
                payload['GRE AW'] = field_contents[2]

        return payload

    except error.HTTPError as e:
        print(f"HTTP Error {e.code} on page {page_num}")
        return {}
    except (
        error.URLError,
        TimeoutError,
        ValueError,
        AttributeError,
        IndexError,
        TypeError,
        RuntimeError,
    ) as e:
        print(f"Error on page {page_num}: {e}")
        return {}


def _concurrent_scraper(worker_func, tasks, is_mapping=False, all_payloads=None):
    """
    Execute scraping tasks concurrently and aggregate successful results.

    :param worker_func: Callable executed per task.
    :type worker_func: collections.abc.Callable
    :param tasks: Task iterable passed to worker function(s).
    :type tasks: collections.abc.Iterable
    :param is_mapping: Whether each task maps to ``all_payloads[task]`` arg pair.
    :type is_mapping: bool
    :param all_payloads: Payload lookup table used when ``is_mapping=True``.
    :type all_payloads: dict | None
    :returns: Combined worker outputs.
    :rtype: list
    """

    all_results = []

    # Set up ThreadPoolExecutor to handle each worker_func slightly differently
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        if is_mapping:
            # Logic for _fetch_result_page
            future_to_task = {
                executor.submit(worker_func, u, all_payloads[u]): u
                for u in tasks
                }
        else:
            # Logic for _fetch_table_page
            future_to_task = {
                executor.submit(worker_func, t): t
                for t in tasks
                }

        # Collect results, print out any errors encountered and move on
        for future in future_to_task:
            try:
                # Iterate futures directly; ordering is not important for downstream consumers.
                data = future.result()
                if data:
                    # Use extend for lists and append for dicts
                    if isinstance(data, list):
                        all_results.extend(data)
                    else:
                        all_results.append(data)
            except (
                error.URLError,
                TimeoutError,
                ValueError,
                AttributeError,
                TypeError,
                RuntimeError,
            ) as e:
                task = future_to_task[future]
                print(f"Task {task} failed with: {e}")

    return all_results


def _get_raw_payloads(data_rows):
    """Build full raw payloads from collected survey rows.

    The function seeds payloads from table rows, then fetches each linked result
    page to fill remaining fields.

    :param data_rows: Parsed survey table rows.
    :type data_rows: list[list[str]]
    :returns: Fully-populated payload dictionaries.
    :rtype: list[dict[str, str]]
    """
    all_payloads = {}
    for row in data_rows:
        payload = {
                'university': '',
                'program': '',
                'degree': '',
                'term': '',
                'date added': '',
                'url': '',
                'application status': '',
                'application status date': '',
                'comments': '',
                'US/International': '',
                'GPA': '',
                'GRE': '',
                'GRE V': '',
                'GRE AW': ''
            }

        try:
            # These are the only three entries needed from the table on /survey/
            # The rest of the fields are easier to parse from /result/ pages
            url = BASE_URL + row[0]
            payload['url'] = url
            payload['date added'] = row[3]
            payload['term'] = row[6]
            all_payloads[url] = payload

        except (IndexError, TypeError):
            # Skip any malformed records
            continue

    # Need the URL from the survey table to pull that particular result page and
    # gather the rest of the data for each record
    all_urls = list(all_payloads.keys())
    all_results = _concurrent_scraper(_fetch_result_page, all_urls,
                                         is_mapping=True,
                                         all_payloads=all_payloads)

    print(f"FINAL RESULTS: {len(all_results)} RECORDS PARSED SUCCESSFULLY")

    return all_results


def scrape_data(min_result_num=None, existing_urls=None):
    """Scrape admissions records from GradCafe.

    :param min_result_num: Optional lower-bound result id filter.
    :type min_result_num: int | None
    :param existing_urls: Optional URL set to skip already-ingested records.
    :type existing_urls: set[str] | None
    :returns: Raw scraped payload list.
    :rtype: list[dict[str, str]]
    """

    t1 = time.time()
    # Collect data from /survey/ pages
    collected_rows = _concurrent_scraper(_fetch_table_page,
                                         range(1, NUM_PAGES_OF_DATA + 1))

    # Then collect data from /result/ pages
    if min_result_num is not None or existing_urls:
        filtered_rows = []
        existing_urls = existing_urls or set()
        for row in collected_rows:
            if not row:
                continue
            url = BASE_URL + row[0]
            result_num = _extract_result_num(url)
            # URL dedupe check handles reruns where source pages still contain old records.
            if url in existing_urls:
                continue
            if min_result_num is not None and result_num is not None:
                if result_num < min_result_num:
                    continue
            filtered_rows.append(row)
        collected_rows = filtered_rows

    raw_payloads = _get_raw_payloads(collected_rows)
    t2 = time.time()

    # Print total number of records retrieved and time to execute, then return
    print(f'Collected {len(raw_payloads)} raw payloads in {t2 - t1:.02f} secs')
    return raw_payloads
