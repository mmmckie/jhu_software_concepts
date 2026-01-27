import requests
import urllib
from urllib import error, request

from bs4 import BeautifulSoup
import re
import json


def _get_table_rows(url: str, query_params: list):
    # Will store all entry rows from the results table for later parsing
    collected_rows = {}

    subset = query_params[:4] # SMALL SUBSET FOR TESTING

    for param in subset:
        url_tmp = url + str(param)
        # Open each URL, print any HTTPErrors (and move on)
        try:
            response = request.urlopen(url_tmp)
            # print(response.code)
            
        except error.HTTPError as e:
            print(f'{e.code} returned from {url_tmp}')
            continue
        
        # Get bytes from request
        content = response.read()
        soup = BeautifulSoup(content, 'html.parser')

        # Grab first table that appears, then get all rows
        # and trim off the single header row of column names
        survey_entries = soup.find('table').find_all('tr')
        data_rows = survey_entries[1:]
        collected_rows[param] = data_rows
    return collected_rows

def _collect_cell_data(input_rows):
    data_rows = {}

    for page in input_rows:
        data_rows[page] = []
        tmp_row = []
        first_row = True
        for row in input_rows[page]:
            # Only new entries will have no attributes in the <tr> tag (Others have class = 'tw-border-none')
            # If new entry, add tmp row to data_rows[page] and clear tmp_row for reuse
            # Don't add on the very first iteration
            if len(row.attrs) == 0:
                if not first_row:
                    data_rows[page].append(tmp_row)
                first_row = False
                tmp_row = []

            # Grab all cells' text and add to the row
            cell_entries = [col.text.strip() for col in row.find_all('td')]

            tmp_row += cell_entries
            

    # Make sure to still add the last row after loop finishes
    data_rows[page].append(tmp_row)

    return data_rows

def scrape_data():
    "Pulls admissions data from GradCafe."

    # (1) Grab 20k pages of results using URL query parameter
    # urls = [f'https://www.thegradcafe.com/survey/?page={i}' for i in range(1,20_000)]
    base_url = 'https://www.thegradcafe.com/survey/'
    query = '?page='

    # (2) For each url, grab all the rows from the table and add them to a list
    collected_rows = _get_table_rows(base_url+query, [i for i in range(1, 20_000)])


    # (3) Now get the text from the cells corresponding to each row
    data_rows = _collect_cell_data(collected_rows)

    # print(data_rows)
    # print(data_rows.keys())
    _create_raw_json(data_rows)
    
    




def _create_raw_json(data):
    for page in data:
        # print(len(data[page]))
        for row in data[page]:
            print(row)
            try:
                university = row[0]
                program_degree = row[1]
                date_added = row[2]
                decision_and_date = row[3]

                supplemental_info = row[5:]
                print(supplemental_info)
                # print(decision_and_date)
            # # accept_reject_date = row[4]
            #     print(f'{university} | {program} | {degree} | {decision} | {decision_date}')
            except:
                print(f'Invalid row format, skipping: {row}')
                continue

            # payload = {
            #             "Program": "",       # MANDATORY
            #             "University": "",    # MANDATORY
            #             "Comments": "",      # OPTIONAL
            #             "Date Added":"",     # MANDATORY
            #             "Status": {"Accepted": acceptance_date, # MANDATORY
            #                     "rejected": rejection_date},
            #             "Program Start": (semester, year), # MANDATORY
            #             "US/International": "", # MANDATORY
            #             "GRE Score": "",        # OPTIONAL
            #             "GRE V Score": "",      # OPTIONAL
            #             "Masters/PhD": "",      # MANDATORY
            #             "GPA": "",              # OPTIONAL
            #             "GRE AW": ""            # OPTIONAL
            # }
                        


if __name__ == '__main__':
    scrape_data()