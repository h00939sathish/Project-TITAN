"""Wrapper: fix sys.path to use .venv_py314 site-packages first."""
import sys
import os

# Remove Hermes venv site-packages from path to avoid cp311/cp314 conflicts
sys.path = [p for p in sys.path if 'hermes-agent' not in p]

# Ensure .venv_py314 site-packages is first
venv314 = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.venv_py314', 'Lib', 'site-packages')
if venv314 in sys.path:
    sys.path.remove(venv314)
sys.path.insert(0, venv314)

# Also add src to path
src = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'src')
if src not in sys.path:
    sys.path.insert(0, src)

print(f"Using Python: {sys.executable}", file=sys.stderr)
print(f"site-packages: {venv314}", file=sys.stderr)

from scripts.run_intraday_research_backtests import main
main()
