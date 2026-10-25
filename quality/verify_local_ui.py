"""Exercise each Streamlit page against the live warehouse without deploying."""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path

from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--profile', required=True)
    args = parser.parse_args()
    settings = json.loads((ROOT / 'deployment/workspace.json').read_text())
    os.environ.update(DATABRICKS_CONFIG_PROFILE=args.profile,
        DATABRICKS_WAREHOUSE_ID=settings['warehouse_id'], HNJOB_LOCAL='true')
    results = []
    app = AppTest.from_file(str(ROOT / 'app/app.py'), default_timeout=180).run()
    for page in ['Overview', 'Skills', 'Compensation', 'Explore ads', 'Ask the data', 'Data coverage']:
        if page != 'Overview': app.radio[0].set_value(page).run()
        errors = [str(e.message) for e in app.exception] + [e.value for e in app.error]
        result = dict(page=page, status='failed' if errors else 'success', errors=errors,
            charts=len(app.get('plotly_chart')), tables=len(app.dataframe),
            metrics=[{'label': m.label, 'value': m.value} for m in app.metric])
        results.append(result)
        print(json.dumps(result), flush=True)
    app.radio[0].set_value('Explore ads').run()
    app.text_input[0].set_value('hnjob-no-match-zzzz-2026')
    app.button(key='FormSubmitter:searchform-Search advertisements').click().run()
    empty_ok = any('No matching ads' in x.value for x in app.info) and not app.exception
    report = dict(checked_at=datetime.now(timezone.utc).isoformat(), pages=results,
        empty_search_passed=bool(empty_ok),
        status='success' if all(r['status']=='success' for r in results) and empty_ok else 'failed',
        method='Streamlit AppTest with the real Databricks backend; not a visual browser screenshot test')
    (ROOT / 'quality/local-ui-results.json').write_text(json.dumps(report, indent=2) + '\n')
    if report['status'] != 'success': raise SystemExit(1)


if __name__ == '__main__': main()
