Flask Routes (board.pages)
==========================

This project does not use a dedicated ``flask_app.py`` file. Route handlers are
implemented in ``src/board/pages.py`` and registered by the app factory in
``src/board/__init__.py``.

Primary routes
--------------

- ``GET /`` and ``GET /analysis``
- ``POST /pull`` and ``POST /pull-data``
- ``POST /update`` and ``POST /update-analysis``

Autodoc
-------

.. automodule:: board.pages
   :members:
   :private-members:
   :undoc-members:
   :show-inheritance:
   :no-index:
