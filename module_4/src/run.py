# Minimal entrypoint: build the Flask app once and run it when invoked as a script.
from board import create_app

app = create_app()

if __name__ == "__main__":
    # Dev defaults: listen on all interfaces so containers/VMs can reach Flask.
    app.run(host="0.0.0.0", port=8080, debug=True)
