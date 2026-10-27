"""Exercise the new local Streamlit workflow with real Databricks reads."""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import time
from streamlit.testing.v1 import AppTest

ROOT=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--profile', required=True)
args=parser.parse_args()
os.environ['DATABRICKS_CONFIG_PROFILE']=args.profile
os.environ['DATABRICKS_WAREHOUSE_ID']=json.loads((ROOT/'deployment/workspace.json').read_text())['warehouse_id']
os.environ['HNJOB_LOCAL']='true'
report=dict(checked_at=datetime.now(timezone.utc).isoformat(), status='failed')
try:
    app=AppTest.from_file(str(ROOT/'app/app.py'),default_timeout=90).run()
    assert not app.exception and not app.error, str(app.exception or app.error)
    app.radio[0].set_value('Your Next Skill').run()
    assert not app.exception and app.multiselect
    app.multiselect[0].set_value(['python','sql']).run()
    button=next(b for b in app.button if b.label=='Find adjacent skills')
    start=time.monotonic();button.click().run(); report['first_screen_seconds']=time.monotonic()-start
    assert not app.exception and not app.error, str(app.exception or app.error)
    assert len(app.subheader)==3
    assert len(app.get('download_button'))==1
    assert len(app.get('link_button'))==9
    start=time.monotonic();app.run();report['cached_screen_seconds']=time.monotonic()-start
    assert not app.exception and not app.error
    report['suggestions']=[s.value for s in app.subheader]
    report['evidence_links']=9
    report['status']='success'
except Exception as exc:
    report['error']=str(exc)
(ROOT/'quality/next-skill-ui-results.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
if report['status']!='success': raise SystemExit(1)
