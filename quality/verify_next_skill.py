"""Read-only live SQL verification against an independent Python set calculation."""
import argparse
from collections import Counter
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'app'))
from backend import Warehouse
from queries import query_for
from next_skill import comparison_periods


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--profile', required=True)
    args = parser.parse_args()
    os.environ['DATABRICKS_CONFIG_PROFILE'] = args.profile
    os.environ['DATABRICKS_WAREHOUSE_ID'] = json.loads((ROOT / 'deployment/workspace.json').read_text())['warehouse_id']
    service = Warehouse()
    report = dict(checked_at=datetime.now(timezone.utc).isoformat(), status='failed', cases=[])
    try:
        coverage = service.query(*query_for('coverage', service.namespace)).frame
        periods = comparison_periods(coverage)
        assert periods['recent_complete'], 'Recent coverage is incomplete'
        report['periods'] = periods
        opts = {k: periods[k] for k in ['prior_start','recent_start','recent_end']}
        # Read bounded post-level rows; join normalized skills only for the independent oracle.
        raw = service.query(f'''SELECT p.comment_id, p.month, p.countries, p.remote_policy, p.seniority,
            s.skill FROM {service.namespace}.post_attributes p LEFT JOIN {service.namespace}.post_skills s
            ON p.comment_id = s.comment_id WHERE p.status = 'success' AND p.is_hiring = true
            AND p.month BETWEEN :start AND :end''', {'start':opts['prior_start'], 'end':opts['recent_end']}, max_rows=50000)
        assert not raw.truncated, 'Oracle input truncated'
        ads = {}
        for row in raw.frame.to_dict('records'):
            ad = ads.setdefault(row['comment_id'], {**row, 'skills':set()})
            if row['skill']: ad['skills'].add(row['skill'])
        for selected, filters in [(['python','sql'], {}), (['python','docker'], {'policy':'remote'}), (['rust'], {'country':'Canada','seniority':'senior'})]:
            picked = set(selected)
            cohort = [a for a in ads.values() if a['skills'] & picked and all(
                not value or value in a[{'country':'countries','policy':'remote_policy','seniority':'seniority'}[key]]
                for key,value in filters.items())]
            recent = [a for a in cohort if a['month'] >= opts['recent_start']]
            previous = [a for a in cohort if a['month'] < opts['recent_start']]
            counts = Counter(s for a in recent for s in a['skills'] - picked)
            expected = sorted([s for s,n in counts.items() if n >= 5], key=lambda s:(-counts[s],s))[:3] if len(recent)>=20 else []
            sql, params = query_for('next_skills',service.namespace, filters, skills=selected, **opts)
            timings=[]
            for _ in range(2):
                start=time.monotonic(); result=service.query(sql,params); timings.append(time.monotonic()-start)
            assert not result.truncated
            frame=result.frame
            assert int(frame.recent_total.iloc[0]) == len(recent)
            assert frame.skill.dropna().tolist() == expected
            for row in frame[frame.skill.notna()].to_dict('records'):
                skill=row['skill']
                assert int(row['recent_mentions']) == counts[skill]
                assert abs(float(row['recent_share_pct']) - 100*counts[skill]/len(recent)) < 1e-6
                assert int(row['previous_mentions']) == sum(skill in a['skills'] for a in previous)
                for i,s in enumerate(sorted(selected)):
                    assert int(row[f'alongside_{i}']) == int(any(skill in a['skills'] and s in a['skills'] for a in recent))
            if expected:
                evidence=service.query(*query_for('next_skill_evidence',service.namespace,filters,skills=selected,candidates=expected,**opts))
                assert not evidence.truncated
                assert not evidence.frame.duplicated(['skill','comment_id']).any()
                for row in evidence.frame.to_dict('records'):
                    assert any(a['comment_id']==row['comment_id'] and row['skill'] in a['skills'] for a in recent)
                assert evidence.frame.groupby('skill').size().to_dict() == {s:3 for s in expected}
            report['cases'].append(dict(skills=selected,filters=filters,query_seconds=timings,
                reference_parity='passed', statement_id=result.statement_id,results=json.loads(frame.to_json(orient='records'))))
        report['status']='success'
    except Exception as exc:
        report['error']=str(exc)
    (ROOT/'quality/next-skill-results.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))
    if report['status']!='success': raise SystemExit(1)


if __name__ == '__main__': main()
