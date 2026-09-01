# Compatibility module for Render default import
import os
import sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

PLATFORM_DIR = os.path.join(BASE_DIR, "platform")
if PLATFORM_DIR not in sys.path:
    sys.path.insert(0, PLATFORM_DIR)

from server.app import app

# gunicorn looks for 'application' by default
application = app
