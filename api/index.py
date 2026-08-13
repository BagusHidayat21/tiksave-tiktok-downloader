import sys
import os

# Add backend directory to path for Vercel Python runtime
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "backend"))

from main import app
