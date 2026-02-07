import threading

from flask import Blueprint, render_template
from flask import redirect, url_for, request

bp = Blueprint('pages', __name__)

from query_data import run_analysis
from main import update_new_records

_PULL_IN_PROGRESS = False
_LAST_PULL_STATUS = None
_LAST_INFO_MESSAGE = None

MSG_PULL_RUNNING = 'Pull Data is currently running. Update Analysis will work once it finishes.'
MSG_ANALYSIS_UPDATED = 'Analysis updated with the latest available data.'


def _run_pull_job():
    global _PULL_IN_PROGRESS, _LAST_PULL_STATUS, _LAST_INFO_MESSAGE
    try:
        _LAST_PULL_STATUS = update_new_records()
        _LAST_INFO_MESSAGE = None
    except Exception as exc:
        _LAST_INFO_MESSAGE = f'Pull Data failed: {exc}'
    finally:
        _PULL_IN_PROGRESS = False

# Set routing address for each page template and create 'active' context variable
# for navbar highlighting

@bp.route('/')
def analysis():
    try:
        results = run_analysis()
        return render_template(
            'pages/analysis.html',
            results=results,
            pull_in_progress=_PULL_IN_PROGRESS,
            update_status=_LAST_PULL_STATUS,
            info_message=_LAST_INFO_MESSAGE,
        )
    except Exception as exc:
        return render_template(
            'pages/analysis.html',
            error=str(exc),
            pull_in_progress=_PULL_IN_PROGRESS,
            update_status=_LAST_PULL_STATUS,
            info_message=_LAST_INFO_MESSAGE,
        )


@bp.route('/pull', methods=['POST'])
def analysis_pull():
    global _PULL_IN_PROGRESS, _LAST_INFO_MESSAGE
    if _PULL_IN_PROGRESS:
        _LAST_INFO_MESSAGE = MSG_PULL_RUNNING
        return redirect(url_for('pages.analysis'))

    _PULL_IN_PROGRESS = True
    _LAST_INFO_MESSAGE = MSG_PULL_RUNNING
    threading.Thread(target=_run_pull_job, daemon=True).start()
    return redirect(url_for('pages.analysis'))


@bp.route('/update', methods=['POST'])
def analysis_update():
    if _PULL_IN_PROGRESS:
        return redirect(url_for('pages.analysis'))
    try:
        results = run_analysis()
        _LAST_INFO_MESSAGE = MSG_ANALYSIS_UPDATED
        return render_template(
            'pages/analysis.html',
            results=results,
            pull_in_progress=_PULL_IN_PROGRESS,
            info_message=MSG_ANALYSIS_UPDATED,
        )
    except Exception as exc:
        return render_template(
            'pages/analysis.html',
            error=str(exc),
            pull_in_progress=_PULL_IN_PROGRESS,
        )
