import requests
import urllib
from urllib import error, request

from bs4 import BeautifulSoup
import re
import json

from concurrent.futures import ThreadPoolExecutor
import time


BASE_URL = 'https://www.thegradcafe.com'
NUM_PAGES_OF_DATA = 2000
MAX_WORKERS = 10 # MAX_WORKERS = 10 is a safe "polite" starting point. 
                 # Increase to 20 or 30 if the server handles it well.
DISALLOWED_PAGES = ['/cgi-bin/',
                    '/index-ad-test.php']

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
        # Use a timeout so the script doesn't hang forever
        response = requests.get(url, timeout=10)
        response.raise_for_status() 
        
        soup = BeautifulSoup(response.text, 'html.parser')
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
            
            cells = [col.get_text().replace('\t','').strip() for col in row.find_all('td')]
            link = row.find('a')
            if link:
                link = link.attrs['href']
                tmp_row.insert(0, link)
                # print(link)
            
            tmp_row.extend(cells)
            
        if tmp_row:
            parsed_data.append(tmp_row)
            
        return parsed_data

    except Exception as e:
        print(f"Error on page {page_num}: {e}")
        return []


def _scrape_table_fast(start_page=1, end_page=NUM_PAGES_OF_DATA):
    """Fetches several pages at a time to collect all data in a list."""
    
    all_results = []
    
    # max_workers=10 is a safe "polite" starting point. 
    # Increase to 20 or 30 if the server handles it well.
    with ThreadPoolExecutor(max_workers= MAX_WORKERS) as executor:
        # Map the function to the range of pages
        future_to_page = {executor.submit(_fetch_table_page, p): p for p in range(start_page, end_page + 1)}
        
        for future in future_to_page:
            data = future.result()
            
            if data:
                all_results += data

    return all_results 


def _create_raw_json(data):
    '''
    Takes the result URLS and some fields from the tables on each page,
    creates the initial payload, then fills it in using the results page.
    Writes all results to json at end.
    '''
    all_payloads = {}
    for row in data:
        payload = {
                'program': '', #
                'university': '', #
                'comments': '', #
                'date added': '', ##############
                'url': '', #
                'application status': '', #
                'application status date': '', #
                'program start': '', #############
                'US/International': '', #
                'GRE': '', #
                'GRE V': '', #
                'degree': '', #
                'GPA': '', #
                'GRE AW': '' #
            }
        
        try:
            url = BASE_URL + row[0]
            payload['url'] = url
            payload['date added'] = row[3]
            
            bubble_fields = row[6]
            pattern = r'[^\n]+'
            matches = re.findall(pattern, bubble_fields)
            filtered_matches = [m for m in matches if 'fall' in m.lower() or 'spring' in m.lower()]
            payload['program start'] = filtered_matches[0]
            
            all_payloads[url] = payload
   
        except:
            # print(f'Invalid row format, skipping: {row}')
            continue


    all_results = _scrape_results_fast(list(all_payloads.keys()), all_payloads)
    print(f"FINAL RESULTS: {len(all_results)} RECORDS PARSED SUCCESSFULLY")
    # print(all_results[:5])
    with open('applicant_data.json', 'w') as f:
        json.dump(all_results, f)


def _fetch_result_page(url, payload):
    """Fetches a single result and parses the data."""
    if _is_restricted_path(url):
        return {}
    
    page_num = url.split('/')[-1]

    try:
        # Use a timeout so the script doesn't hang forever
        response = requests.get(url, timeout=10)
        response.raise_for_status() 
        
        soup = BeautifulSoup(response.text, 'html.parser')
        entries = soup.find('dl').find_all('div')
        
        if not entries:
            return {}
        
        # Parse the rows immediately into the clean format
        payload = {'url': url}
        for i, entry in enumerate(entries):
            if i in [0, 1, 2, 3, 4, 5, 6, 8]:
                field_contents = entry.find('dd')
                if field_contents:
                    field_contents = field_contents.get_text().replace('\n','').replace('\t','')
                else:
                    continue
                # print(i, field_contents)
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
                    pattern = r'[^0-9/]'
                    clean_date = re.sub(pattern, '', field_contents)
                    payload['application status date'] = clean_date
                elif i == 6:
                    payload['GPA'] = field_contents
                elif i == 8:
                    payload['comments'] = field_contents
            elif i == 7:
                field_contents = [e for e in entry.find_all('li')]
                spans = [e.find('span').next_sibling.next_sibling for e in field_contents]
                field_contents = [s.get_text().strip() for s in spans]
                payload['GRE'] = field_contents[0]
                payload['GRE V'] = field_contents[1]
                payload['GRE AW'] = field_contents[2]
            
        return payload
    
    except Exception as e:
        print(f"Error on page {page_num}: {e}")
        return {}


def _scrape_results_fast(urls: list, all_payloads):
    """Fetches several pages at a time to collect all data in a list."""
    
    all_results = []

    with ThreadPoolExecutor(max_workers= MAX_WORKERS) as executor:
        # Map the function to the range of pages
        future_to_page = {executor.submit(_fetch_result_page, u, all_payloads[u]): u for u in urls}
        
        for future in future_to_page:
            data = future.result()
            if data:
                all_results.append(data)

    return all_results

def scrape_data():
    "Pulls admissions data from GradCafe."


    t_start = time.time()
    collected_rows = _scrape_table_fast()
    t_end = time.time()

    print(f'Collected {len(collected_rows)} records in {t_end - t_start:.02f} secs')

    _create_raw_json(collected_rows)
    t_end = time.time()
    print(f'Finished creating initial JSON in {t_end - t_start:.02f} secs')

if __name__ == '__main__':
    scrape_data()