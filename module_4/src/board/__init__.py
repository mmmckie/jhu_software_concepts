"""Flask application factory for the analysis web interface."""

from flask import Flask

from board import pages

def create_app(
    *,
    test_config=None,
    run_analysis_fn=None,
    update_new_records_fn=None,
):
    """Create and configure the Flask application.

    :param test_config: Optional config dictionary applied after app creation.
    :type test_config: dict | None
    :param run_analysis_fn: Optional override for analysis service function.
    :type run_analysis_fn: collections.abc.Callable | None
    :param update_new_records_fn: Optional override for pull/load service.
    :type update_new_records_fn: collections.abc.Callable | None
    :returns: Configured Flask app instance.
    :rtype: flask.Flask
    """
    app = Flask(__name__)
    if test_config:
        app.config.update(test_config)
    if run_analysis_fn is not None:
        app.config["RUN_ANALYSIS_FN"] = run_analysis_fn
    if update_new_records_fn is not None:
        app.config["UPDATE_NEW_RECORDS_FN"] = update_new_records_fn

    app.register_blueprint(pages.bp)
    return app
