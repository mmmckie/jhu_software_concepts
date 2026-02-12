"""Data cleaning utilities for scraped GradCafe records."""

import re

import json


def _remove_whitespace(str_):
    """Remove newline and tab characters from a string.

    :param str_: Raw string value to normalize.
    :type str_: str
    :returns: Input string with ``\\n`` and ``\\t`` removed.
    :rtype: str
    """

    pattern = '[\n\t]'
    output = re.sub(pattern, '', str_)
    return output


def clean_data(raw_data: list):
    """Normalize raw scraped payloads into clean application records.

    The function standardizes the term field, removes extra whitespace from
    every value, trims application status date strings to date-only format,
    and converts known sentinel values (for optional fields) to ``None``.

    :param raw_data: Raw list of application payload dictionaries.
    :type raw_data: list[dict]
    :returns: Cleaned payload dictionaries in original order.
    :rtype: list[dict]
    """

    cleaned_data = []
    for payload in raw_data:
        # Find term start date by finding entries surrounded by \n sequences in ['term']
        term_start = payload['term']
        pattern = r'[^\n]+'
        matches = re.findall(pattern, term_start)

        # Only retain matches that have 'fall' or 'spring' in them
        # Will get only 1 result representing term start in the list
        filtered_matches = [m for m in matches if 'fall' in m.lower() or 'spring' in m.lower()]
        term = filtered_matches[0]

        # Create new payload without newline/tab sequences and set start term
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

    # Return list of cleaned payloads
    return cleaned_data


def save_data(cleaned_payloads, path='applicant_data.json'):
    """Write cleaned payloads to disk as JSON.

    :param cleaned_payloads: Cleaned records to persist.
    :type cleaned_payloads: list[dict]
    :param path: Output JSON path.
    :type path: str
    :returns: ``None``.
    :rtype: None
    """

    with open(path, 'w') as f:
        json.dump(cleaned_payloads, f)


def load_data():
    """Load cleaned payloads from ``applicant_data.json``.

    :returns: Parsed JSON payload list.
    :rtype: list[dict]
    """
    with open('applicant_data.json', 'r') as f:
        clean_data = json.load(f)
    return clean_data
