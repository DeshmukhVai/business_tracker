"""
WSGI entry point.

On PythonAnywhere, point the "WSGI configuration file" to import `application`
from this module (see README.md for the exact steps). This file deliberately
contains no local machine paths — PythonAnywhere's own WSGI file (which you
edit in their web UI) is responsible for adding the project directory to
sys.path.
"""

from app import app as application

if __name__ == "__main__":
    application.run()
