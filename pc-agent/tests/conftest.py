import os
import sys

# Make the pc-agent modules importable as top-level modules, the way agent.py imports them.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
