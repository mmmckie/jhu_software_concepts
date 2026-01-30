import re

import json


def _remove_whitespace(str_):
    '''Remove any instances of \n or \t characters.'''
    pattern = '[\n\t]'
    output = re.sub(pattern, '', str_)
    return output


def clean_data(raw_data: list):
    """
    Converts data into a structured format.
    
    Arguments:
    raw_data: list of dicts containing raw entries

    Returns:
    cleaned_data: list of dicts containing cleaned entries
    
    """
    cleaned_data = []
    for payload in raw_data:
        # Find term start by finding fields surrounded by \n sequences
        term_start = payload['term']
        pattern = r'[^\n]+'
        matches = re.findall(pattern, term_start)
        # Only retain matches that have 'fall' or 'spring' in them
        # Will get only 1 result representing term start in the list
        filtered_matches = [m for m in matches if 'fall' in m.lower() or 'spring' in m.lower()]
        term = filtered_matches[0]

        # Remove extra newline and tab sequences from all other fields, and set start term
        new_payload = {k: _remove_whitespace(v) for k, v in payload.items()}
        new_payload['term'] = term

        # Retain only the date (not 'on <date> via <email/phone/etc>')
        app_status_date = new_payload['application status date']
        new_payload['application status date'] = re.sub('[^0-9/]', '', app_status_date)

        # Set optional fields to None if they came in empty
        if len(new_payload['comments']) == 0:
            new_payload['comments'] = None

        if new_payload['GPA'] == '0.00':
            new_payload['GPA'] = None

        if new_payload['GRE'] == '0':
            new_payload['GRE'] = None

        if new_payload['GRE V'] == '0':
            new_payload['GRE V'] = None

        if new_payload['GRE AW'] == '0.00':
            new_payload['GRE AW'] = None

        cleaned_data.append(new_payload)

    return cleaned_data


def save_data(cleaned_payloads):
    "Saves cleaned data into applicant_data.json."
    with open('applicant_data.json', 'w') as f:
        json.dump(cleaned_payloads, f)


def load_data():
    "Loads cleaned data from applicant_data.json."
    with open('applicant_data.json', 'r') as f:
        clean_data = json.load(f)
    return clean_data