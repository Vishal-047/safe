import os
import sys

# Add project root and platform directory to sys.path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

PLATFORM_DIR = os.path.join(BASE_DIR, "platform")
if PLATFORM_DIR not in sys.path:
    sys.path.insert(0, PLATFORM_DIR)

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from server.app import app
