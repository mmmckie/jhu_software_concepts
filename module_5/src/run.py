# Minimal entrypoint: build the Flask app once and run it when invoked as a script.
"""Flask application entry point."""

import os

from board import create_app

app = create_app()

if __name__ == "__main__":
    # Dev defaults: listen on all interfaces so containers/VMs can reach Flask.
    debug = os.getenv("FLASK_DEBUG", "0").strip().lower() in {"1", "true", "yes", "on"}
    app.run(host="0.0.0.0", port=8080, debug=debug)
