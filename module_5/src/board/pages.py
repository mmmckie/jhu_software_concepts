"""Route handlers for the analysis dashboard and pull/update actions."""

import threading
import traceback
from pathlib import Path

import psycopg
from flask import Blueprint, current_app, jsonify, redirect, render_template, request

bp = Blueprint('pages', __name__)

try:
    from query_data import run_analysis
    from main import update_new_records
    from load_data import stream_jsonl_to_postgres
except ModuleNotFoundError:
    from src.query_data import run_analysis
    from src.main import update_new_records
    from src.load_data import stream_jsonl_to_postgres

_PULL_LOCK = threading.Lock()
# Shared state coordinates async pull requests across browser/API routes.
_PULL_IN_PROGRESS = False
_PULL_MESSAGE_PENDING = False
_PULL_ERROR_PENDING = None
_BOOTSTRAP_IN_PROGRESS = False
_BOOTSTRAP_MESSAGE_PENDING = False
_BOOTSTRAP_ERROR_PENDING = None

_STATE_KEY_MAP = {
    'pull_in_progress': '_PULL_IN_PROGRESS',
    'pull_message_pending': '_PULL_MESSAGE_PENDING',
    'pull_error_pending': '_PULL_ERROR_PENDING',
    'bootstrap_in_progress': '_BOOTSTRAP_IN_PROGRESS',
    'bootstrap_message_pending': '_BOOTSTRAP_MESSAGE_PENDING',
    'bootstrap_error_pending': '_BOOTSTRAP_ERROR_PENDING',
}


def _state_get(key):
    with _PULL_LOCK:
        return globals()[_STATE_KEY_MAP[key]]


def _state_set(**kwargs):
    with _PULL_LOCK:
        for key, value in kwargs.items():
            globals()[_STATE_KEY_MAP[key]] = value


def _is_api_route():
    """Check whether the current request targets JSON API endpoints.

    :returns: ``True`` for ``/pull-data`` or ``/update-analysis`` routes.
    :rtype: bool
    """
    return request.path in {"/pull-data", "/update-analysis"}


def _run_analysis_service():
    """Resolve and execute the configured analysis function.

    :returns: Analysis result payload.
    :rtype: dict
    """
    fn = current_app.config.get("RUN_ANALYSIS_FN", run_analysis)
    return fn()


def _update_new_records_service():
    """Resolve and execute the configured pull/update function.

    :returns: Pull/update status payload.
    :rtype: dict
    """
    fn = current_app.config.get("UPDATE_NEW_RECORDS_FN", update_new_records)
    return fn()


def _bootstrap_jsonl_path():
    """Return canonical JSONL path used for first-time DB table/bootstrap load."""
    return Path(__file__).resolve().parents[1] / 'llm_extend_applicant_data.jsonl'


def _is_missing_admissions_table_error(exc):
    """Return True when the error indicates the admissions table is missing."""
    text = str(exc).lower()
    return (
        'relation "admissions" does not exist' in text
        or "relation 'admissions' does not exist" in text
    )


def _start_bootstrap_worker():
    """Start background table/bootstrap load once for fresh databases."""
    if _state_get('bootstrap_in_progress'):
        return

    def _worker():
        try:
            stream_jsonl_to_postgres(str(_bootstrap_jsonl_path()))
        except (RuntimeError, ValueError, OSError, TypeError) as exc:
            _state_set(bootstrap_error_pending=f'Initial database setup failed: {exc}')
            traceback.print_exc()
        finally:
            _state_set(bootstrap_in_progress=False)

    _state_set(
        bootstrap_in_progress=True,
        bootstrap_message_pending=True,
        bootstrap_error_pending=None,
    )
    threading.Thread(target=_worker, daemon=True).start()


def _empty_results():
    """Return a zeroed analysis payload for guarded/busy template responses.

    :returns: Default analysis result map with all metrics set to zero.
    :rtype: dict[str, object]
    """
    return {
        "total_records": 0,
        "fall_2026_applicants": 0,
        "international_percentage": 0.0,
        "american_fall_2026_gpa": 0.0,
        "fall_2025_acceptance_rate": 0.0,
        "fall_2026_acceptance_gpa": 0.0,
        "jhu_cs_masters": 0,
        "ivy_2026_compsci_phds": 0,
        "ivy_2026_compsci_phds_llm_fields": 0,
        "ivy_2026_compsci_phds_raw_fields": 0,
        "fall_2025_applicants": 0,
        "spring_2025_applicants": 0,
        "masters_acceptance": {"with_gpa": 0.0, "no_gpa": 0.0},
        "phd_acceptance": {"with_gpa": 0.0, "no_gpa": 0.0},
        "average_metrics": {"gpa": 0.0, "gre": 0.0, "gre_v": 0.0, "gre_aw": 0.0},
    }

# Set routing address for each page template and create 'active' context variable
# for navbar highlighting

@bp.route('/')
@bp.route('/analysis')
def analysis():
    """Render the analysis dashboard page.

    Pending status/error messages from asynchronous pull operations are consumed
    on this request and included in template context.

    :returns: Rendered HTML response.
    :rtype: str
    """
    info_message = None
    error_message = None
    if _state_get('pull_message_pending'):
        # Message is one-shot to avoid repeating stale notices after refresh.
        info_message = 'Pull Data is currently running. Update Analysis will work once it finishes.'
        _state_set(pull_message_pending=False)
    if _state_get('bootstrap_message_pending'):
        info_message = (
            'Initial database setup is running in the background. '
            'The page will refresh automatically once data is loaded.'
        )
        _state_set(bootstrap_message_pending=False)
    pending_error = _state_get('pull_error_pending')
    if pending_error:
        error_message = pending_error
        _state_set(pull_error_pending=None)
    bootstrap_error = _state_get('bootstrap_error_pending')
    if bootstrap_error and not error_message:
        error_message = bootstrap_error
        _state_set(bootstrap_error_pending=None)
    try:
        pull_in_progress = _state_get('pull_in_progress')
        bootstrap_in_progress = _state_get('bootstrap_in_progress')
        results = _run_analysis_service()
        if error_message:
            return render_template(
                'pages/analysis.html',
                error=error_message,
                results=results,
                pull_in_progress=pull_in_progress,
                bootstrap_in_progress=bootstrap_in_progress,
                info_message=info_message,
            )
        return render_template(
            'pages/analysis.html',
            results=results,
            pull_in_progress=pull_in_progress,
            bootstrap_in_progress=bootstrap_in_progress,
            info_message=info_message,
        )
    except (RuntimeError, ValueError, OSError, TypeError) as exc:
        if _is_missing_admissions_table_error(exc):
            _start_bootstrap_worker()
            info_message = (
                'Initial database setup is running in the background. '
                'The page will refresh automatically once data is loaded.'
            )
            return render_template(
                'pages/analysis.html',
                results=_empty_results(),
                pull_in_progress=_state_get('pull_in_progress'),
                bootstrap_in_progress=_state_get('bootstrap_in_progress'),
                info_message=info_message,
            )
        pull_in_progress = _state_get('pull_in_progress')
        bootstrap_in_progress = _state_get('bootstrap_in_progress')
        return render_template(
            'pages/analysis.html',
            error=str(exc),
            pull_in_progress=pull_in_progress,
            bootstrap_in_progress=bootstrap_in_progress,
            info_message=info_message,
        )


@bp.route('/pull', methods=['POST'])
@bp.route('/pull-data', methods=['POST'])
def analysis_pull():
    """Handle pull-data requests for both browser and API clients.

    Browser ``/pull`` requests are executed asynchronously and redirected back
    to the dashboard. API ``/pull-data`` requests are handled synchronously and
    return JSON status.

    :returns: Redirect/HTML response for browser routes or JSON for API routes.
    :rtype: flask.Response | tuple[flask.Response, int]
    """
    is_api = _is_api_route()
    already_running = _state_get('pull_in_progress')
    if already_running:
        if is_api:
            return jsonify({"busy": True, "ok": False}), 409
        return (
            render_template(
                'pages/analysis.html',
                pull_in_progress=True,
                bootstrap_in_progress=_state_get('bootstrap_in_progress'),
                results=_empty_results(),
                info_message='Pull Data is already running. Please wait for it to finish.',
            ),
            409,
        )
    if not is_api:
        update_fn = current_app.config.get("UPDATE_NEW_RECORDS_FN", update_new_records)

        def _pull_worker(fn):
            """Execute pull work in a background thread.

            :param fn: Pull/update callable to invoke.
            :type fn: collections.abc.Callable
            :returns: ``None``.
            :rtype: None
            """
            try:
                fn()
            except (RuntimeError, ValueError, OSError, TypeError, psycopg.Error) as exc:
                _state_set(pull_error_pending=f'Pull Data failed: {exc}')
                traceback.print_exc()
            finally:
                _state_set(pull_in_progress=False)

        _state_set(
            pull_in_progress=True,
            pull_message_pending=True,
            pull_error_pending=None,
        )
        # Fire-and-forget worker keeps browser flow responsive.
        threading.Thread(target=_pull_worker, args=(update_fn,), daemon=True).start()
        return redirect('/')

    try:
        _state_set(pull_in_progress=True)
        update_status = _update_new_records_service()
        _run_analysis_service()
        _state_set(pull_in_progress=False)
        return jsonify(
            {
                "busy": False,
                "ok": True,
                "records": update_status.get("records", 0),
                "status": update_status.get("status"),
            }
        ), 200
    except (RuntimeError, ValueError, OSError, TypeError, psycopg.Error) as exc:
        _state_set(pull_in_progress=False)
        return jsonify({"busy": False, "ok": False, "error": str(exc)}), 500


@bp.route('/update', methods=['POST'])
@bp.route('/update-analysis', methods=['POST'])
def analysis_update():
    """Handle analysis-refresh requests for browser and API clients.

    Update requests are blocked while a pull is in progress. Browser requests
    render template responses; API requests return JSON statuses.

    :returns: Redirect/HTML response for browser routes or JSON for API routes.
    :rtype: flask.Response | tuple[flask.Response, int]
    """
    pull_in_progress = _state_get('pull_in_progress')
    if pull_in_progress:
        if _is_api_route():
            return jsonify({"busy": True, "ok": False}), 409
        # Browser path redirects so banner message can be rendered on GET /analysis.
        _state_set(pull_message_pending=True)
        return redirect('/')
    try:
        results = _run_analysis_service()
        if _is_api_route():
            return jsonify({"busy": False, "ok": True}), 200
        return render_template(
            'pages/analysis.html',
            results=results,
            pull_in_progress=_state_get('pull_in_progress'),
            bootstrap_in_progress=_state_get('bootstrap_in_progress'),
            info_message='Analysis updated with the latest available data.',
        )
    except (RuntimeError, ValueError, OSError, TypeError) as exc:
        if _is_api_route():
            return jsonify({"busy": False, "ok": False, "error": str(exc)}), 500
        return render_template(
            'pages/analysis.html',
            error=str(exc),
            pull_in_progress=_state_get('pull_in_progress'),
            bootstrap_in_progress=_state_get('bootstrap_in_progress'),
        )
