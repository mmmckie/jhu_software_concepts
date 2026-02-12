import json
from pathlib import Path

from scrape import scrape_data
from clean import clean_data, save_data, load_data
from load_data import stream_jsonl_to_postgres, get_existing_urls, get_max_result_page

import subprocess


def _run_LLM_pipeline(input_json_path, output_jsonl_path):
    '''
    Calls llm_hosting/app.py via subprocess to pass the data to local LLM
    for cleaning/standardization.
    '''

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
    path_obj = Path(path)
    if path_obj.exists():
        with open(path_obj, 'r') as f:
            existing = json.load(f)
        if not isinstance(existing, list):
            existing = []
    else:
        existing = []
    existing.extend(records)
    with open(path_obj, 'w') as f:
        json.dump(existing, f)


def _append_jsonl_records(source_jsonl_path, target_jsonl_path):
    with open(source_jsonl_path, 'r') as source_file, open(
        target_jsonl_path, 'a'
    ) as target_file:
        for line in source_file:
            if line.strip():
                target_file.write(line)


def update_new_records():
    existing_urls = get_existing_urls()
    max_result_page = get_max_result_page()
    min_result_num = max_result_page + 1 if max_result_page is not None else None

    raw_data = scrape_data(min_result_num=min_result_num, existing_urls=existing_urls)
    if not raw_data:
        return {'status': 'no_new'}

    cleaned_data = clean_data(raw_data)
    src_dir = Path(__file__).resolve().parent
    new_json_path = src_dir / 'applicant_data_new.json'
    new_jsonl_path = src_dir / 'llm_extend_applicant_data_new.jsonl'
    full_json_path = src_dir / 'applicant_data.json'
    full_jsonl_path = src_dir / 'llm_extend_applicant_data.jsonl'

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
