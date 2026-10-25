"""Run the app's bounded read-only queries and one end-to-end model question."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'app'))
from backend import Warehouse
from queries import query_for


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--profile', required=True)
    parser.add_argument('--skip-chat', action='store_true')
    args = parser.parse_args()
    settings = json.loads((ROOT / 'deployment/workspace.json').read_text())
    os.environ['DATABRICKS_CONFIG_PROFILE'] = args.profile
    os.environ['DATABRICKS_WAREHOUSE_ID'] = settings['warehouse_id']
    os.environ['HNJOB_CHAT_MODEL'] = settings['selected_model']
    service = Warehouse()
    filters = dict(start='2026-04', end='2026-09', country='', policy='', seniority='')
    cases = [(name, {}) for name in ['metadata', 'options', 'coverage', 'monthly', 'skills',
             'policies', 'seniority', 'countries', 'salary_options', 'explorer', 'explorer_count']]
    cases += [('skill_trend', {'skills': ['python', 'rust']}),
              ('growth', dict(prior_start='2026-04', recent_start='2026-07', recent_end='2026-09', minimum=20)),
              ('salaries', dict(currency='USD', period='annual', compensation_type='base'))]
    def run(case):
        name, options = case
        statement, params = query_for(name, service.namespace, filters, **options)
        try:
            result = service.query(statement, params)
            return dict(query=name, status='success', rows=len(result.frame), truncated=result.truncated,
                statement_id=result.statement_id, sample=json.loads(result.frame.head(2).to_json(orient='records')))
        except Exception as exc:
            return dict(query=name, status='failed', error=str(exc))
    with ThreadPoolExecutor(max_workers=3) as pool:
        reports = list(pool.map(run, cases))
    for row in reports:
        print(json.dumps({k:v for k,v in row.items() if k != 'sample'}), flush=True)
    chat = None
    if not args.skip_chat:
        question = 'Which five skills grew fastest in share of hiring ads in July-September 2026 versus April-June 2026? Require at least 20 mentions each quarter. Show counts, shares and percentage-point increase.'
        try:
            plan = service.plan_answer(question, {**filters, 'latest_complete_month':'2026-09'}, [])
            if not plan.get('sql'): raise RuntimeError('Expected a supported query, received clarification: ' + str(plan))
            result = service.query(plan['sql'], max_rows=200)
            canonical = service.query(*query_for('growth', service.namespace, filters,
                prior_start='2026-04', recent_start='2026-07', recent_end='2026-09', minimum=20)).frame.head(5)
            expected = canonical.set_index('skill')
            actual = result.frame.set_index('skill')
            assert list(actual.index) == list(expected.index), 'Chat ranking differs from reference SQL'
            required = ['previous_total', 'recent_total', 'previous_mentions', 'recent_mentions', 'growth_pp']
            assert all(c in actual for c in required), 'Chat answer must expose reference counts and denominators'
            for col in required:
                assert (abs(actual[col].astype(float) - expected[col].astype(float)) < 0.015).all(), f'Chat {col} differs from reference SQL'
            chat = dict(status='success', question=question, plan=plan, rows=json.loads(result.frame.to_json(orient='records')),
                        statement_id=result.statement_id, reference_sql_parity='passed')
        except Exception as exc:
            chat = dict(status='failed', question=question, error=str(exc))
        print(json.dumps(chat), flush=True)
    report = dict(checked_at=datetime.now(timezone.utc).isoformat(), queries=reports, chat=chat,
                  status='success' if all(r['status']=='success' for r in reports) and (chat is None or chat['status']=='success') else 'failed')
    (ROOT / 'quality/app-live-results.json').write_text(json.dumps(report, indent=2) + '\n')
    if report['status'] != 'success': raise SystemExit(1)


if __name__ == '__main__': main()
