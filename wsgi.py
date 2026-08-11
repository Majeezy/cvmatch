import sys
import os

# Replace YOURUSERNAME with your actual PythonAnywhere username
path = '/home/YOURUSERNAME/job_application_assistant'
if path not in sys.path:
    sys.path.insert(0, path)

os.environ.setdefault('FLASK_SECRET', 'change-this-to-a-long-random-string')

from server import app as application
