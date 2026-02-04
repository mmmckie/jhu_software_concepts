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
        return render_template("pages/analysis.html", active='analysis', results=results)
    except Exception as exc:
        return render_template("pages/analysis.html", active='analysis', error=str(exc))


@bp.route("/analysis/refresh", methods=["POST"])
def analysis_refresh():
    try:
        update_status = update_new_records()
        results = run_analysis()
        return render_template(
            "pages/analysis.html",
            active='analysis',
            results=results,
            update_status=update_status,
        )
    except Exception as exc:
        return render_template(
            "pages/analysis.html",
            active='analysis',
            error=str(exc),
        )
