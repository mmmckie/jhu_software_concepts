Name: Max McKie (mmckie2)

Module Info: Module 2 Assignment: Web Scraping due on 02/01/2026 at 11:59 PM EST

Approach: 
________________________________________________________________________________
scrape.py-
This module first imports the requisite libraries: urllib for URL 
handling and making requests, BeautifulSoup for parsing/extracting HTML elements,
concurrent.futures.ThreadPoolExecutor for paralellization, and time for timing
how long it takes to gather all the raw data. It then defines a few global variables,
including the base URL for TheGradCafe, the number of pages of survey results to
scrape, the maximum number of workers allowed for pulling data in parallel, a
list of disallowed paths as designated by robots.txt from TheGradCafe's site, and
headers to send with the HTTP requests to mimic a standard Chrome browser to
prevent 403 errors. The function _is_restricted_path() is defined next, which
accepts a URL as input and returns True or False depending on whether that URL
is contained in DISALLOWED_PAGES from robots.txt.

________________________________________________________________________________
clean.py - 

________________________________________________________________________________
main.py - 

________________________________________________________________________________
app.py - 

Known Bugs:
There are no known bugs.

================================================================================
INSTRUCTIONS FOR RUNNING:
--------------------------------------------------------------------------------
(1) Install Python 3.12.3
(2) $git clone git@github.com:mmmckie/jhu_software_concepts.git
(3) Ensure current working directory is jhu_software_concepts/module_2
(4) $pip install -r requirements.txt
(5) $python main.py
================================================================================