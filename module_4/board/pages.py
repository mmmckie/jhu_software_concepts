from flask import Blueprint, render_template
from flask import redirect, url_for, request

bp = Blueprint('pages', __name__)

from query_data import run_analysis
from main import update_new_records

_PULL_IN_PROGRESS = False

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
    try:
        results = run_analysis()
        return render_template(
            'pages/analysis.html',
            results=results,
            pull_in_progress=_PULL_IN_PROGRESS,
        )
    except Exception as exc:
        return render_template(
            'pages/analysis.html',
            error=str(exc),
            pull_in_progress=_PULL_IN_PROGRESS,
        )


@bp.route('/pull', methods=['POST'])
@bp.route('/pull-data', methods=['POST'])
def analysis_pull():
    global _PULL_IN_PROGRESS
    if _PULL_IN_PROGRESS:
        return (
            render_template(
                'pages/analysis.html',
                pull_in_progress=_PULL_IN_PROGRESS,
                results=_empty_results(),
                info_message='Pull Data is already running. Please wait for it to finish.',
            ),
            409,
        )
    try:
        _PULL_IN_PROGRESS = True
        update_status = update_new_records()
        results = run_analysis()
        _PULL_IN_PROGRESS = False
        return render_template(
            'pages/analysis.html',
            results=results,
            update_status=update_status,
            info_message='Pull Data complete. You can now click Update Analysis.',
            pull_in_progress=_PULL_IN_PROGRESS,
        )
    except Exception as exc:
        _PULL_IN_PROGRESS = False
        return render_template(
            'pages/analysis.html',
            error=str(exc),
            pull_in_progress=_PULL_IN_PROGRESS,
        )


@bp.route('/update', methods=['POST'])
@bp.route('/update-analysis', methods=['POST'])
def analysis_update():
    if _PULL_IN_PROGRESS:
        return (
            render_template(
                'pages/analysis.html',
                pull_in_progress=_PULL_IN_PROGRESS,
                results=_empty_results(),
                info_message='Pull Data is currently running. Update Analysis will work once it finishes.',
            ),
            409,
        )
    try:
        results = run_analysis()
        return render_template(
            'pages/analysis.html',
            results=results,
            pull_in_progress=_PULL_IN_PROGRESS,
            info_message='Analysis updated with the latest available data.',
        )
    except Exception as exc:
        return render_template(
            'pages/analysis.html',
            error=str(exc),
            pull_in_progress=_PULL_IN_PROGRESS,
        )
