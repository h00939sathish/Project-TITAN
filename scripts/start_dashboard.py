"""Start the TITAN dashboard."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dashboard.server import run
run(host="127.0.0.1", port=8082)
