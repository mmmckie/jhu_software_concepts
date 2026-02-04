from pathlib import Path
import sys

from flask import Blueprint, render_template
from flask import redirect, url_for, request

bp = Blueprint("pages", __name__)

# Allow module_1 Flask app to import module_3 analysis utilities.
module_3_path = Path(__file__).resolve().parents[2] / "module_3"
if str(module_3_path) not in sys.path:
    sys.path.append(str(module_3_path))

from query_data import run_analysis
from main import update_new_records

_PULL_IN_PROGRESS = False

# Set routing address for each page template and create 'active' context variable
# for navbar highlighting

@bp.route("/")
def home():
    return render_template("pages/home.html", active = 'home',)

@bp.route("/contact")
def contact():
    return render_template("pages/contact.html", active = 'contact')

@bp.route("/projects")
def projects():
    return render_template("pages/projects.html", active = 'projects')

@bp.route("/analysis")
def analysis():
    try:
        results = run_analysis()
        return render_template(
            "pages/analysis.html",
            active='analysis',
            results=results,
            pull_in_progress=_PULL_IN_PROGRESS,
        )
    except Exception as exc:
        return render_template(
            "pages/analysis.html",
            active='analysis',
            error=str(exc),
            pull_in_progress=_PULL_IN_PROGRESS,
        )


@bp.route("/analysis/pull", methods=["POST"])
def analysis_pull():
    global _PULL_IN_PROGRESS
    try:
        _PULL_IN_PROGRESS = True
        update_status = update_new_records()
        results = run_analysis()
        _PULL_IN_PROGRESS = False
        return render_template(
            "pages/analysis.html",
            active='analysis',
            results=results,
            update_status=update_status,
            info_message="Pull Data complete. You can now click Update Analysis.",
            pull_in_progress=_PULL_IN_PROGRESS,
        )
    except Exception as exc:
        _PULL_IN_PROGRESS = False
        return render_template(
            "pages/analysis.html",
            active='analysis',
            error=str(exc),
            pull_in_progress=_PULL_IN_PROGRESS,
        )


@bp.route("/analysis/update", methods=["POST"])
def analysis_update():
    if _PULL_IN_PROGRESS:
        return render_template(
            "pages/analysis.html",
            active='analysis',
            pull_in_progress=_PULL_IN_PROGRESS,
            info_message="Pull Data is currently running. Update Analysis will work once it finishes.",
        )
    try:
        results = run_analysis()
        return render_template(
            "pages/analysis.html",
            active='analysis',
            results=results,
            pull_in_progress=_PULL_IN_PROGRESS,
            info_message="Analysis updated with the latest available data.",
        )
    except Exception as exc:
        return render_template(
            "pages/analysis.html",
            active='analysis',
            error=str(exc),
            pull_in_progress=_PULL_IN_PROGRESS,
        )
