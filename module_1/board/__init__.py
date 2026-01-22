
# from flask import Flask

# def create_app():
#     app = Flask(__name__)

#     from app.blueprints.main import main_bp
#     app.register_blueprint(main_bp)

#     return app


from flask import Flask

from board import pages

def create_app():
    app = Flask(__name__)

    app.register_blueprint(pages.bp)
    return app