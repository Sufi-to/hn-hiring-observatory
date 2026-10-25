"""Managed-app entry point; local review uses the repository's run_local.py."""
import os
import sys

if os.environ.get('DATABRICKS_APP_NAME'):
    from runtime_check import run_checks
    run_checks()

os.execv(sys.executable, [sys.executable, '-m', 'streamlit', 'run', 'app.py',
    '--server.address', '0.0.0.0', '--server.port', os.environ.get('DATABRICKS_APP_PORT', '8000'),
    '--server.headless', 'true'])
