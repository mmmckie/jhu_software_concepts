Setup & Run Guide
=================

Prerequisites
-------------

- Python 3.12+
- PostgreSQL running locally or reachable via connection URL
- Dependencies installed from ``module_5/requirements.txt``

Install
-------

From ``jhu_software_concepts/module_5``:

.. code-block:: bash

   pip install -r requirements.txt

Required environment variables
------------------------------

The application can run with local defaults, but these variables are recommended
for explicit and reproducible configuration:

- ``DATABASE_URL``:
  PostgreSQL connection used by ``src/query_data.py`` and ``src/load_data.py``.
  Example:

  .. code-block:: bash

     export DATABASE_URL="postgresql://postgres:password@localhost:5432/grad_data"

- ``DATABASE_ADMIN_URL``:
  Admin connection used by ``src/load_data.py`` for database provisioning when
  ``DATABASE_URL`` is not set. Defaults to ``dbname=postgres``.

  .. code-block:: bash

     export DATABASE_ADMIN_URL="postgresql://postgres:password@localhost:5432/postgres"

Optional LLM-hosting variables (for ``src/llm_hosting/app.py``):

- ``MODEL_REPO``
- ``MODEL_FILE``
- ``N_THREADS``
- ``N_CTX``
- ``N_GPU_LAYERS``
- ``CANON_UNIS_PATH``
- ``CANON_PROGS_PATH``
- ``PORT``

Run the app
-----------

From ``jhu_software_concepts/module_5``:

.. code-block:: bash

   python src/run.py

The Flask app listens on ``http://localhost:8080``.

Run tests
---------

From ``jhu_software_concepts/module_5``:

.. code-block:: bash

   pytest

Run only marked groups (entire supported suite):

.. code-block:: bash

   pytest -m "web or buttons or analysis or db or integration"
