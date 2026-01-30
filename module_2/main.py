from scrape import scrape_data
from clean import clean_data, save_data, load_data

import subprocess

def _run_LLM_pipeline():
    '''
    Calls llm_hosting/app.py via subprocess to pass the data to local LLM
    for cleaning/standardization.
    '''

    try:
        # Cmd line args to execute when launching app.py
        cmd_args = ["--file", "../applicant_data.json", "--stdout"]

        # Open the output file in write mode and trigger app.py
        with open("llm_extended_applicant_data.jsonl", "w") as output_file:
            subprocess.run(
                ["python", "app.py"] + cmd_args,
                cwd="llm_hosting",
                stdout=output_file,  # This replaces the ">" operator
                check=True
            )

        print("Pipeline executed successfully!")
       
    except subprocess.CalledProcessError as e:
        print(f"The second script failed with error code: {e.returncode}")


def main():

    # Collect raw data in JSON format from TheGradCafe
    raw_data = scrape_data()

    # Clean data to obtain clear, consistent formatting
    cleaned_data = clean_data(raw_data)

    # Write cleaned JSON entries to applicant_data.json
    save_data(cleaned_data)

    # Trigger local LLM to standardize program/university fields and write 
    # output to llm_extended_applicant_data.jsonl
    _run_LLM_pipeline()


if __name__ == '__main__':
    main()
