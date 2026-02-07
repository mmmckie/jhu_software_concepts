from flask import Blueprint, render_template

bp = Blueprint("pages", __name__)

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