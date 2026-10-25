"""Run the local review app using an explicitly selected Databricks profile."""
import argparse
import json
import os
from pathlib import Path
import sys

root = Path(__file__).resolve().parent
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--profile', required=True, help='Databricks profile selected by the user')
parser.add_argument('--port', type=int, default=8501)
args = parser.parse_args()
settings = json.loads((root / 'deployment/workspace.json').read_text())
os.environ['DATABRICKS_CONFIG_PROFILE'] = args.profile
os.environ.setdefault('DATABRICKS_WAREHOUSE_ID', settings['warehouse_id'])
os.environ.setdefault('HNJOB_NAMESPACE', settings['catalog'] + '.' + settings['schema'])
os.environ.setdefault('HNJOB_CHAT_MODEL', settings['selected_model'])
os.environ['HNJOB_LOCAL'] = 'true'
os.chdir(root / 'app')
os.execv(sys.executable, [sys.executable, '-m', 'streamlit', 'run', 'app.py',
    '--server.address', '127.0.0.1', '--server.port', str(args.port),
    '--server.headless', 'true', '--browser.gatherUsageStats', 'false'])
