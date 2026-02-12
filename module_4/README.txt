Steps to run analysis webpage on localhost:

(1) Install PostgreSQL and ensure the permissions for localhost are set to 'trust'
(2) Install Python 3.12.3
(3) $git clone git@github.com:mmmckie/jhu_software_concepts.git
(4) Ensure current working directory is jhu_software_concepts/module_3
(5) $pip install -r requirements.txt
(6) $python run.py

Sphinx docs:

(1) Ensure current working directory is jhu_software_concepts/module_4
(2) $pip install -r docs/requirements.txt
(3) $cd docs
(4) $make html
(5) Open docs/_build/html/index.html in your browser
