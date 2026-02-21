import os
import sys
from datetime import datetime

# Keep Sphinx autodoc imports stable by making project `src/` importable.
PROJECT_ROOT = os.path.abspath('..')
SRC_ROOT = os.path.join(PROJECT_ROOT, 'src')
if SRC_ROOT not in sys.path:
    sys.path.insert(0, SRC_ROOT)

project = 'JHU Software Concepts - Module 5'
author = 'Max M. McKie'
copyright = f"{datetime.now().year}, {author}"
release = '1.0.0'

extensions = [
    'sphinx.ext.autodoc',
    'sphinx.ext.napoleon',
    'sphinx.ext.viewcode',
    'sphinx.ext.autosummary',
]

autosummary_generate = True
autodoc_member_order = 'bysource'
autodoc_typehints = 'description'
# Mock heavy/runtime-only deps so docs can build without full app environment.
autodoc_mock_imports = [
    "psycopg",
    "bs4",
    "llama_cpp",
    "huggingface_hub",
]
autodoc_default_options = {
    "members": True,
    "undoc-members": True,
    "private-members": True,
    "show-inheritance": True,
}

templates_path = ['_templates']
exclude_patterns = ['_build', 'Thumbs.db', '.DS_Store']

html_theme = 'alabaster'
html_static_path = ['_static']
