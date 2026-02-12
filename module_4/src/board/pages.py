import threading
import traceback

from flask import Blueprint, current_app, jsonify, redirect, render_template, request

bp = Blueprint('pages', __name__)

try:
    from query_data import run_analysis
    from main import update_new_records
except ModuleNotFoundError:
    from src.query_data import run_analysis
    from src.main import update_new_records

_PULL_IN_PROGRESS = False
_PULL_MESSAGE_PENDING = False
_PULL_LOCK = threading.Lock()
_PULL_ERROR_PENDING = None


def _is_api_route():
    return request.path in {"/pull-data", "/update-analysis"}


def _run_analysis_service():
    fn = current_app.config.get("RUN_ANALYSIS_FN", run_analysis)
    return fn()


def _update_new_records_service():
    fn = current_app.config.get("UPDATE_NEW_RECORDS_FN", update_new_records)
    return fn()

def _empty_results():
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
    global _PULL_MESSAGE_PENDING, _PULL_ERROR_PENDING
    info_message = None
    error_message = None
    if _PULL_MESSAGE_PENDING:
        info_message = 'Pull Data is currently running. Update Analysis will work once it finishes.'
        _PULL_MESSAGE_PENDING = False
    if _PULL_ERROR_PENDING:
        error_message = _PULL_ERROR_PENDING
        _PULL_ERROR_PENDING = None
    try:
        with _PULL_LOCK:
            pull_in_progress = _PULL_IN_PROGRESS
        results = _run_analysis_service()
        if error_message:
            return render_template(
                'pages/analysis.html',
                error=error_message,
                results=results,
                pull_in_progress=pull_in_progress,
                info_message=info_message,
            )
        return render_template(
            'pages/analysis.html',
            results=results,
            pull_in_progress=pull_in_progress,
            info_message=info_message,
        )
    except Exception as exc:
        with _PULL_LOCK:
            pull_in_progress = _PULL_IN_PROGRESS
        return render_template(
            'pages/analysis.html',
            error=str(exc),
            pull_in_progress=pull_in_progress,
            info_message=info_message,
        )


@bp.route('/pull', methods=['POST'])
@bp.route('/pull-data', methods=['POST'])
def analysis_pull():
    global _PULL_IN_PROGRESS, _PULL_MESSAGE_PENDING, _PULL_ERROR_PENDING
    is_api = _is_api_route()
    with _PULL_LOCK:
        already_running = _PULL_IN_PROGRESS
    if already_running:
        if is_api:
            return jsonify({"busy": True, "ok": False}), 409
        return (
            render_template(
                'pages/analysis.html',
                pull_in_progress=_PULL_IN_PROGRESS,
                results=_empty_results(),
                info_message='Pull Data is already running. Please wait for it to finish.',
            ),
            409,
        )
    if not is_api:
        update_fn = current_app.config.get("UPDATE_NEW_RECORDS_FN", update_new_records)
        app_obj = current_app._get_current_object()

        def _pull_worker(app, fn):
            global _PULL_IN_PROGRESS, _PULL_ERROR_PENDING
            try:
                with app.app_context():
                    fn()
            except Exception as exc:
                _PULL_ERROR_PENDING = f'Pull Data failed: {exc}'
                traceback.print_exc()
            finally:
                with _PULL_LOCK:
                    _PULL_IN_PROGRESS = False

        with _PULL_LOCK:
            _PULL_IN_PROGRESS = True
            _PULL_MESSAGE_PENDING = True
            _PULL_ERROR_PENDING = None
        threading.Thread(target=_pull_worker, args=(app_obj, update_fn)).start()
        return redirect('/')

    try:
        with _PULL_LOCK:
            _PULL_IN_PROGRESS = True
        update_status = _update_new_records_service()
        _run_analysis_service()
        with _PULL_LOCK:
            _PULL_IN_PROGRESS = False
        return jsonify(
            {
                "busy": False,
                "ok": True,
                "records": update_status.get("records", 0),
                "status": update_status.get("status"),
            }
        ), 200
    except Exception as exc:
        with _PULL_LOCK:
            _PULL_IN_PROGRESS = False
        return jsonify({"busy": False, "ok": False, "error": str(exc)}), 500


@bp.route('/update', methods=['POST'])
@bp.route('/update-analysis', methods=['POST'])
def analysis_update():
    global _PULL_MESSAGE_PENDING
    with _PULL_LOCK:
        pull_in_progress = _PULL_IN_PROGRESS
    if pull_in_progress:
        if _is_api_route():
            return jsonify({"busy": True, "ok": False}), 409
        _PULL_MESSAGE_PENDING = True
        return redirect('/')
    try:
        results = _run_analysis_service()
        if _is_api_route():
            return jsonify({"busy": False, "ok": True}), 200
        return render_template(
            'pages/analysis.html',
            results=results,
            pull_in_progress=_PULL_IN_PROGRESS,
            info_message='Analysis updated with the latest available data.',
        )
    except Exception as exc:
        if _is_api_route():
            return jsonify({"busy": False, "ok": False, "error": str(exc)}), 500
        return render_template(
            'pages/analysis.html',
            error=str(exc),
            pull_in_progress=_PULL_IN_PROGRESS,
        )
