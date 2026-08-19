"""
pytest configuration and shared fixtures.
"""

import sys
from pathlib import Path

# Add app/ directory to sys.path so test files can import modules directly
app_dir = Path(__file__).parent.parent / "app"
if str(app_dir) not in sys.path:
    sys.path.insert(0, str(app_dir))
