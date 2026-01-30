Name: Max McKie (mmckie2)

Module Info: Module 2 Assignment: Web Scraping due on 02/01/2026 at 11:59 PM EST

================================================================================
Approach: 
--------------------------------------------------------------------------------
scrape.py-
This module first imports the requisite libraries: urllib for URL 
handling and making requests, BeautifulSoup for parsing/extracting HTML elements,
concurrent.futures.ThreadPoolExecutor for parallelization, and time for timing
how long it takes to gather all the raw data. It then defines a few global variables,
including the base URL for TheGradCafe, the number of pages of survey results to
scrape, the maximum number of workers allowed for pulling data in parallel, a
list of disallowed paths as designated by robots.txt from TheGradCafe's site, and
headers to send with the HTTP requests to mimic a standard Chrome browser to
prevent 403 errors. The function _is_restricted_path() is defined next, which
accepts a URL as input and returns True or False depending on whether that URL
is contained in DISALLOWED_PAGES from robots.txt. Next are two functions
(_fetch_table_page() and _fetch_result_page()) for scraping data from the /survey/
and /result/ pages, respectively. _fetch_table_page() accepts an int to
designate which page to put in the URL query parameter for 'page' and then creates
a urllib Request object using the URL and defined HEADERS to mimic a standard
browser and prevent 403 errors. urlopen then obtains the HTTPResponse object
and the bytes content is read and passed to BeautifulSoup using the HTML parser.
The <table> object containing all of the rows of data entries is then obtained
using soup.find('table'), and if nothing is found then the function returns an
empty list. If the table is found, then all the rows are retrieved with find_all('tr'),
and the header row containing only column names is skipped via indexing. An
empty list, 'parssed_data', is instantiated to contain all of the raw parsed data
from each entry, and another empty list 'tmp_row' is created for joining the data
from multiple rows together if they are part of the same record. A for loop is
created to iterate over each row collected from the table, and an if statement
checks if the row has no attrs since new entries begin with a <tr> tag and 
additional information for the same entry is contained in following 
<tr class='tw-border-none'> tags. If it is a new entry according to this check,
then tmp_row will be added to parsed_data unless tmp_row is still empty, which
only happens on the first iteration. Then tmp_row will be reinstantiated to an
empty list to begin collecting data for the current entry. The individual column
entries in each row are collected using get_text() on each of the <td> tags contained
in the row using list comprehension. Next row.find('a') is called to obtain the
link to the /result/ page corresponding to the present record and the url is
prepended to the list. After the for loop finishes, tmp_row will be appended to
parsed_data once more to make sure the very last entry is collected, and then
parsed_data is returned. _fetch_result_page accepts a URL and a dict (data entry
in json format) as arguments. It again first checks that the url is not disallowed
by robots.txt, and then collects the page number of the URL so that if an error
occurs on any page a message can be printed to the user designating which page
encountered an issue. Next, a Request object is again created with the URL and
the same HEADERS parameter, and the HTML content is retrieved again using urlopen
and BeautifulSoup. All the data entries on the page are contained in <div> tags
within a <dl> tag, so these are retrieved with soup.find('dl').find_all('div').
If no entries are found, the function returns an empty dict. Otherwise, the payload
is updated with the requisite data by iterating through the entries using 
enumerate(). The data is contained in indices 1-8, with only index 7 having a
slightly different format. For all indices except 7, the data can be grabbed
directly by finding the <dd> element and getting the text, then assigning that
datum as the value of the relevant key in the payload. All 3 GRE scores are
stored in the 7th <div> inside of <span> tags contained within 3 separate <li>
tags, which are found using BeautifulSoup and list comprehensions along with
get_text(), and then the payload is updated with the 3 GRE score values, and
then the payload is returned. All logic in this function starting from the point
of calling urlopen is wrapped in a 'try' block, and two 'except' blocks will handle
any HTTPErrors or other errors and print information out to the user. A fourth
function, _concurrent_scraper() is used to handle calling _fetch_table_page()
and _fetch_result_page() concurrently for more efficient execution. As arguments
it accepts the function to be called, the numbers to be included in each url
(which /survey/ or /results/ page to open), a boolean to indicate the format of
the argument mapping passed to executor.submit(), and an optional argument
'all_payloads' that only passed if 'worker_func' is _fetch_result_page(). Next
a context manager opens a ThreadPoolExecutor object with max_workers set to
MAX_WORKERS, and if 'is_mapping' is true when using _fetch_result_page() as the
worker_func, then a dict 'future_to_task' will be created using a dict comprehension
with the keys as Future objects given the worker_func and respective arguments 
for each argument in 'tasks', and the number of each task as the value. Creating
these Future objects in the keys will begin execution of the worker_func in a
separate thread. If 'is_mapping' is False, then _fetch_table_page() will be called
concurrently using identical logic, only with separate arguments passed to 
worker_func. Next there is a for loop that iterates through the future_to_task
dict, and for each Future object retrieves the returned result with future.result().
If the data is not empty, then an if statement will check wither the returned 
object is a list or a dict, in which cases it will either extend 'all_results' 
or append the dict to 'all_results' respectively. This process of collecting the
individual results is wrapped in a try block within the for loop to print out
any errors that occur and move on to the next iteration. Once this is done,
'all_results' is returned. The fifth function, _get_raw_payloads(), accepts a
list of rows of data as returned by calling _concurrent_scraper() with 
_fetch_table_page() as the worker func (i.e., it accepts a list of lists, where
each sublist contains a row of information collected from a /survey/ page table).
It then begins by instantiating an empty dict to store all json payloads that will
eventually be created from the data, and for each row in the input data, a fresh
payload is created with all of the fields to be collected as keys and empty strings
as values. A try block is then opened in case of malformed entries, and the URL
for the /result/ page is created using the BASE_URL with the href value at index
0 of the row of data. The 'url' field of the initially empty payload is then set
to this value, and the 'date added' and 'term' fields are filled out by indexing
the list/row of data currently being processed. Only these fields are filled in
using data from the /survey/ page because the other fields are available and
easier to parse from the /result/ pages. This payload is then added to 
'all_payloads' with the URL as the key in order to easily identify which /result/
page should be used to fill out the rest of each payload. The list of all URLs
is obtained by calling (list(all_payloads.keys())), and then the list of all
payloads, fully filled out (but still not cleaned), is obtained by calling
_concurrent_scraper() with _fetch_result_page as the worker func and passing it
the list of all urls and the dict containing all payloads as arguments. There is
then a print statement informing the user how many records were successfully
collected/parsed, and then the list of all payloads is returned. Finally,
the function scrape_data() is used to tie all of these functions together so
that scraping can be achieved with a single function call. Within scrape_data(),
a timestamp is first created using time.time() so that a print statement can
inform the user how long the process of collecting data took once the execution
completes. Next, the list of rows of data from the /survey/ pages is retrieved
by calling _concurrent_scraper() with _fetch_table_page as the worker_func and
passing range(1, NUM_PAGES_OF_DATA) as the 'tasks' argument. NUM_PAGES_OF_DATA
is set to 2000 by default, and with 21 records per page should provide ~40k rows
of data once the process is complete. Once the rows of data are retrieved from
the /survey/ pages, _get_raw_payloads() is called with that data passed as the
argument to collect a list of all the raw, uncleaned JSON payloads as a result.
Another timestamp is created here and a print statement informs the user how many
records were collected and how many seconds it took, and then the list of raw
JSON payloads is returned.

________________________________________________________________________________
clean.py - 
This module begins by importing re for using regex expressions to clean the raw
JSON payloads and the json module for saving/loading the data to/from json files.
A helper function, _remove_whitespace() is first created that accepts a string 
as an argument and uses a simple regex expression to identify and replace any
newline or tab character sequences with empty strings. The next function,
clean_data(), accepts a list of raw data payloads (the output of scrape_data() 
from scrape.py) as input. It first creates a list to store all of the payloads
of cleaned data, and then a for loop iterates over all of the raw payloads. First,
the term start is extracted by using a regex pattern with re.findall() to
identify all of the portions of the text (different field entries) that are
separated by any number of newline characters and return them in a list. Since
there are multiple fields included here, the term start is identified using a
list comprehension that only retains values that include 'fall' or 'spring' 
(after calling lower() to avoid any capitalization issues). There will be only
one element returned in all cases, so the term is obtained by indexing the 0th
element from this list of filtered matches. Then, a brand new payload is created
using a dict comprehension to copy all of the keys from the dirty payload and
assigning the values as _remove_whitespace(v) from each value. The term start date
was isolated first because calling _remove_whitespace() on the 'term' field would
have made parsing the term start a bit more difficult. Next, the 'term' field of
the new payload is overwritten using the value just extracted before the new
payload was created. Next, the 'application status date' field is cleaned by
using a regex expression that replaces any character that is not a digit or forward
slash with an empty string. This is to keep only the acceptance/rejection date
in DD/MM/YYYY format, rather than something like 'on DD/MM/YYYY via email'.
Next there several if statements that check for the default values for 'comments',
'GRE', 'GRE V', and 'GRE AW' ("", '0.00', '0', '0', and '0.00', respectively)
since these are optional fields, and if no value was entered then these will be
overwritten to None. Once the new payload is fully filled out, then it is appended
to the list of cleaned data, and once the for loop terminates then the list of
cleaned payloads will be returned. The next two functions, save_data() and
load_data(), operate very similarly. save_data() accepts the list of clean payloads
as input and then writes the data to applicant_data.json using json.dump().
load_data() opens applicant_data.json in read mode, uses json.load() to load the
cleaned data into memory, and returns the clean data.

________________________________________________________________________________
main.py - 
This script first imports scrape_data() from scrape.py and all functions from
clean.py, as well as the subprocess module. There is one helper function,
_run_LLM_pipeline(), that is used to call app.py from within the llm_hosting/
subdirectory. Inside a try block, there is a list of cmd line args to add onto
the call to launch app.py. Next the output file 'llm_extended_applicant_data.json'
is opened in write mode with a context manager, and subprocess.run() is called to
create a new process with the working directory set to llm_hosting/ that launches
app.py and routes the stdout to the output file currently open in write mode. If
this process is successful, then a print statment will inform the user that the
pipeline executed successfully, and if not an except block will print the error
to the user. The main() function first collects the raw JSON payloads using
scrape_data() from scrape.py, then the cleaned data is obtained by passing the
raw data to clean_data() from clean.py. Next, save_data() writes this cleaned
data to applicant_data.json, and lastly a call to _run_LLM_pipeline() kicks off
the process to have a local Llama model attempt to standardize the program and
university names. Finally, there is an 'if name equals main' statement to ensure
the main() function is only executed when this module is executed as a script.

________________________________________________________________________________
app.py - 
The only changes to app.py were:
(1) _call_llm() had to be modified to provide the LLM with 'program' and 'university'
    fields separately, since they were not combined into a single field in the output
    of clean_data()
(2) More examples were added to FEW_SHOTS to improve LLM performance
(3) The default SYSTEM_PROMPT was given to Gemini with the task of optimizing
    it for use by a small local LLM.

================================================================================
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