from flask import Flask

from board import pages

def create_app(
    *,
    test_config=None,
    run_analysis_fn=None,
    update_new_records_fn=None,
):
    app = Flask(__name__)
    if test_config:
        app.config.update(test_config)
    if run_analysis_fn is not None:
        app.config["RUN_ANALYSIS_FN"] = run_analysis_fn
    if update_new_records_fn is not None:
        app.config["UPDATE_NEW_RECORDS_FN"] = update_new_records_fn

    app.register_blueprint(pages.bp)
    return app
