from urllib.request import urlopen
from urllib import error, request
from bs4 import BeautifulSoup

from concurrent.futures import ThreadPoolExecutor
import time


BASE_URL = 'https://www.thegradcafe.com'
NUM_PAGES_OF_DATA = 2000
MAX_WORKERS = 10 # MAX_WORKERS = 10 is a safe "polite" starting point. 
                 # Increase to 20 or 30 if the server handles it well.
DISALLOWED_PAGES = ['/cgi-bin/',
                    '/index-ad-test.php']

# This header makes the scraper look like a standard Chrome browser
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
}
def _is_restricted_path(url):
    '''Checks for URL paths restricted by robots.txt'''
    for restricted_path in DISALLOWED_PAGES:
        if restricted_path in url:
            return True
    return False

def _fetch_table_page(page_num):
    """Fetches a single page and parses the table rows."""
    url = f"{BASE_URL}/survey/?page={page_num}"
    if _is_restricted_path(url):
        return []
    
    try:
        # Create a Request object with the headers
        req = request.Request(url, headers=HEADERS)
        # Use a timeout so the script doesn't hang forever
        with urlopen(req, timeout=10) as response:
            content = response.read() # Returns bytes
            # BeautifulSoup handles the byte-to-string conversion automatically
            soup = BeautifulSoup(content, 'html.parser')
        table = soup.find('table')
        
        if not table:
            return []

        # Get all rows, skip the header
        rows = table.find_all('tr')[1:]
        
        # Parse the rows immediately into the clean format
        parsed_data = []
        tmp_row = []
        for row in rows:
            if len(row.attrs) == 0:
                if tmp_row:
                    parsed_data.append(tmp_row)
                tmp_row = []
            
            cells = [col.get_text() for col in row.find_all('td')]
            link = row.find('a')
            if link:
                link = link.attrs['href']
                tmp_row.insert(0, link)
            
            tmp_row.extend(cells)
            
        if tmp_row:
            parsed_data.append(tmp_row)
            
        return parsed_data
    
    except error.HTTPError as e:
        print(f"HTTP Error {e.code} on page {page_num}")

    except Exception as e:
        print(f"Error on page {page_num}: {e}")
        return []


def _scrape_table_fast(start_page=1, end_page=NUM_PAGES_OF_DATA):
    """Fetches several pages at a time to collect all data in a list."""
    
    all_results = []
    
    with ThreadPoolExecutor(max_workers= MAX_WORKERS) as executor:
        # Map the function to the range of pages
        future_to_page = {executor.submit(_fetch_table_page, p):
                          p for p in range(start_page, end_page + 1)}
        
        for future in future_to_page:
            data = future.result()
            
            if data:
                all_results += data

    return all_results 


def _get_raw_payloads(data):
    '''
    Takes the result URLS and some fields from the tables on each page,
    creates the initial payload, then fills it in using the results page.
    Writes all results to json at end.
    '''
    all_payloads = {}
    for row in data:
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
            # The rest of the fields are easier to parse from /result/
            url = BASE_URL + row[0]
            payload['url'] = url
            payload['date added'] = row[3]
            payload['term'] = row[6]            
            all_payloads[url] = payload
   
        except:
            # print(f'Invalid row format, skipping: {row}')
            continue

    all_results = _scrape_results_fast(list(all_payloads.keys()), all_payloads)
    print(f"FINAL RESULTS: {len(all_results)} RECORDS PARSED SUCCESSFULLY")

    return all_results    


def _fetch_result_page(url, payload):
    """Fetches a single result and parses the data."""
    if _is_restricted_path(url):
        return {}
    
    page_num = url.split('/')[-1]

    try:
        # Create a Request object with the headers
        req = request.Request(url, headers=HEADERS)

        # urllib.request.urlopen acts as a context manager
        with urlopen(req, timeout=10) as response:
            content = response.read() # Returns bytes
            # BeautifulSoup handles the byte-to-string conversion automatically
            soup = BeautifulSoup(content, 'html.parser')
        entries = soup.find('dl').find_all('div')
        
        if not entries:
            return {}
        
        # Parse the entries and store raw data in the payload dict, then return
        payload['url'] = url
        for i, entry in enumerate(entries):
            if i in [0, 1, 2, 3, 4, 5, 6, 8]:
                
                # Check that the field has text content to avoid errors
                field_contents = entry.find('dd')
                if field_contents:
                    field_contents = field_contents.get_text()
                else:
                    continue

                if i == 0:
                    payload['university'] = field_contents
                elif i == 1:
                    payload['program'] = field_contents
                elif i == 2:
                    payload['degree'] = field_contents
                elif i == 3:
                    payload['US/International'] = field_contents
                elif i == 4:
                    payload['application status'] = field_contents
                elif i == 5:
                    payload['application status date'] = field_contents
                elif i == 6:
                    payload['GPA'] = field_contents
                elif i == 8:
                    payload['comments'] = field_contents
            
            elif i == 7: # The GRE scores have a slightly different format
                field_contents = [e for e in entry.find_all('li')]
                spans = [e.find('span').next_sibling.next_sibling for e in field_contents]
                field_contents = [s.get_text() for s in spans]
                payload['GRE'] = field_contents[0]
                payload['GRE V'] = field_contents[1]
                payload['GRE AW'] = field_contents[2]
            
        return payload
    
    except error.HTTPError as e:
        print(f"HTTP Error {e.code} on page {page_num}")

    except Exception as e:
        print(f"Error on page {page_num}: {e}")
        return {}


def _scrape_results_fast(urls: list, all_payloads):
    """Fetches several pages at a time to collect all data in a list."""
    
    all_results = []

    with ThreadPoolExecutor(max_workers= MAX_WORKERS) as executor:
        # Map the function to the range of pages
        future_to_page = {executor.submit(_fetch_result_page, u, all_payloads[u]):
                           u for u in urls}
        
        for future in future_to_page:
            data = future.result()
            if data:
                all_results.append(data)

    return all_results

def scrape_data():
    "Pulls admissions data from GradCafe."

    t1 = time.time()
    collected_rows = _scrape_table_fast()
    raw_payloads = _get_raw_payloads(collected_rows)
    t2 = time.time()

    print(f'Collected {len(raw_payloads)} raw payloads in {t2 - t1:.02f} secs')
    return raw_payloads