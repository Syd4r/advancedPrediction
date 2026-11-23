'''
Create a Flask app and register the main blueprint.
'''
from flask import Flask
from dotenv import load_dotenv
from .views import main_blueprint

load_dotenv()

def create_app():
    '''
    Creates the Flask app
    '''
    app = Flask(__name__)
    app.register_blueprint(main_blueprint)
    return app
