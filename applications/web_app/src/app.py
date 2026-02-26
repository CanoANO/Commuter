#!/usr/bin/env python3

import os
import sys
from pathlib import Path
from flask import Flask
from .config import get_settings
from .routes import main_routes, plan_routes, system_routes

PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

def create_app():
    template_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), 'templates'))
    app = Flask(__name__, template_folder=template_dir)
    settings = get_settings()
    
    app.config['ENV'] = settings.FLASK_ENV
    app.config['DEBUG'] = settings.DEBUG
    
    app.register_blueprint(main_routes)
    app.register_blueprint(plan_routes)
    app.register_blueprint(system_routes)
    
    return app

app = create_app()

if __name__ == '__main__':
    settings = get_settings()
    app.run(debug=settings.DEBUG, host='0.0.0.0', port=8000)
