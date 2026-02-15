"""Orchestration workflow for scrape, clean, normalize, and load operations."""

# Supports both full initial ingestion (`main`) and incremental refresh (`update_new_records`).
import json
from pathlib import Path

from scrape import scrape_data
from clean import clean_data, save_data, load_data
from load_data import stream_jsonl_to_postgres, get_existing_urls, get_max_result_page

import subprocess


def _run_LLM_pipeline(input_json_path, output_jsonl_path):
    """Run the local LLM normalization script over a JSON input file.

    The function invokes ``llm_hosting/app.py`` as a subprocess and writes
    line-delimited JSON output incrementally to the requested file.

    :param input_json_path: Path to JSON input payload.
    :type input_json_path: str
    :param output_jsonl_path: Path where normalized JSONL should be written.
    :type output_jsonl_path: str
    :returns: ``None``.
    :rtype: None
    """

    try:
        # Cmd line args to execute when launching app.py
        cmd_args = ['--file', f'../{Path(input_json_path).name}', '--stdout']
        script_dir = Path(__file__).resolve().parent
        llm_hosting_dir = script_dir / 'llm_hosting'

        # Open the output file in write mode and trigger app.py
        with open(output_jsonl_path, 'w') as output_file:
            try:
                subprocess.run(
                    ['python', 'app.py'] + cmd_args,
                    cwd='llm_hosting',
                    stdout=output_file,  # This replaces the ">" operator
                    check=True
                )
            except FileNotFoundError:
                # Support invocation from outside src/ (e.g., `python src/run.py`).
                subprocess.run(
                    ['python', 'app.py'] + cmd_args,
                    cwd=str(llm_hosting_dir),
                    stdout=output_file,
                    check=True
                )

        print('Pipeline executed successfully!')
       
    except subprocess.CalledProcessError as e:
        print(f'The second script failed with error code: {e.returncode}')


def main():
    """Execute the full initial ingestion pipeline.

    This function scrapes fresh data, cleans it, saves canonical JSON, and runs
    the LLM normalization stage to produce JSONL output.

    :returns: ``None``.
    :rtype: None
    """

    # Collect raw data in JSON format from TheGradCafe
    raw_data = scrape_data()

    # Clean data to obtain clear, consistent formatting
    cleaned_data = clean_data(raw_data)

    # Write cleaned JSON entries to applicant_data.json
    save_data(cleaned_data, 'applicant_data.json')

    # Trigger local LLM to standardize program/university fields and write 
    # output to llm_extended_applicant_data.jsonl
    _run_LLM_pipeline(
        'applicant_data.json',
        'llm_extend_applicant_data.jsonl',
    )


def _append_json_records(records, path):
    """Append new records to an existing JSON array file.

    If the destination file exists but is not a JSON list, it is treated as an
    empty list before appending.

    :param records: Records to append.
    :type records: list[dict]
    :param path: Target JSON file path.
    :type path: str | pathlib.Path
    :returns: ``None``.
    :rtype: None
    """
    path_obj = Path(path)
    if path_obj.exists():
        with open(path_obj, 'r') as f:
            existing = json.load(f)
        # Recover gracefully if an unexpected JSON object/string is present.
        if not isinstance(existing, list):
            existing = []
    else:
        existing = []
    existing.extend(records)
    with open(path_obj, 'w') as f:
        json.dump(existing, f)


def _append_jsonl_records(source_jsonl_path, target_jsonl_path):
    """Append non-empty JSONL lines from one file to another.

    :param source_jsonl_path: Source JSONL file.
    :type source_jsonl_path: str | pathlib.Path
    :param target_jsonl_path: Destination JSONL file.
    :type target_jsonl_path: str | pathlib.Path
    :returns: ``None``.
    :rtype: None
    """
    with open(source_jsonl_path, 'r') as source_file, open(
        target_jsonl_path, 'a'
    ) as target_file:
        for line in source_file:
            if line.strip():
                target_file.write(line)


def update_new_records():
    """Scrape and ingest only records that are newer than current database data.

    Existing URLs and maximum result page are used to reduce duplicate work.
    New records are cleaned, normalized with the LLM pipeline, appended to
    cumulative JSON/JSONL datasets, and inserted into PostgreSQL.

    :returns: Status dictionary describing whether records were added.
    :rtype: dict[str, str | int]
    """
    existing_urls = get_existing_urls()
    max_result_page = get_max_result_page()
    # Start scraping from the first unseen result number when DB state is known.
    min_result_num = max_result_page + 1 if max_result_page is not None else None

    raw_data = scrape_data(min_result_num=min_result_num, existing_urls=existing_urls)
    if not raw_data:
        # Keep response minimal for UI/API callers that only need status.
        return {'status': 'no_new'}

    cleaned_data = clean_data(raw_data)
    src_dir = Path(__file__).resolve().parent
    new_json_path = src_dir / 'applicant_data_new.json'
    new_jsonl_path = src_dir / 'llm_extend_applicant_data_new.jsonl'
    full_json_path = src_dir / 'applicant_data.json'
    full_jsonl_path = src_dir / 'llm_extend_applicant_data.jsonl'

    # Persist both delta artifacts and cumulative datasets for reproducibility.
    save_data(cleaned_data, str(new_json_path))
    _run_LLM_pipeline(str(new_json_path), str(new_jsonl_path))
    _append_json_records(cleaned_data, str(full_json_path))
    _append_jsonl_records(
        str(new_jsonl_path), str(full_jsonl_path)
    )
    stream_jsonl_to_postgres(str(new_jsonl_path))
    return {'status': 'updated', 'records': len(cleaned_data)}


if __name__ == '__main__':
    main()
