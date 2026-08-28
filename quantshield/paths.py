import os
from pathlib import Path

ROOT = Path(os.environ.get('QUANTSHIELD_ROOT') or Path(__file__).resolve().parent.parent)
DATA = ROOT / 'data'
PORTFOLIO = DATA / 'portfolio'
MONITOR = DATA / 'monitor'
INTRADAY = DATA / 'intraday'
JOURNAL = DATA / 'journal'
RESEARCH = DATA / 'research'
DASHBOARD = ROOT / 'dashboard'
