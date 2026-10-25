"""Verify deployed data/model access using the app's own injected identity."""
import json
from backend import Warehouse


def run_checks():
    report = {'data': 'pending', 'chat': 'pending'}
    try:
        service = Warehouse()
        ns = service.namespace
        result = service.query(f"""SELECT current_user() AS execution_identity,
          count(*) AS posts, count_if(status = 'success' AND is_hiring) AS hiring_ads,
          min(month) AS first_month, max(month) AS last_month,
          (SELECT count(*) FROM {ns}.post_skills) AS skill_mentions,
          (SELECT count(*) FROM {ns}.post_countries) AS country_mentions,
          (SELECT count(*) FROM {ns}.post_salaries) AS salary_ranges,
          (SELECT count(*) FROM {ns}.post_processing_coverage) AS processing_months,
          (SELECT count(*) FROM {ns}.ingestion_coverage) AS ingestion_months
          FROM {ns}.post_attributes""").frame
        counts = result.iloc[0]
        assert int(counts.posts) > 0 and int(counts.processing_months) > 0
        report.update(data='passed', counts=json.loads(result.to_json(orient='records'))[0])
        try:
            filters = dict(start=counts.first_month, end=counts.last_month,
                           country='', policy='', seniority='')
            plan = service.plan_answer('How many distinct successful hiring advertisements are in the entire dataset, across all months? Return one count column.', filters, [])
            assert plan.get('sql'), 'Chat returned no SQL for the count smoke question'
            answer = service.query(plan['sql'], max_rows=200).frame
            assert answer.shape == (1, 1) and int(answer.iloc[0, 0]) == int(counts.hiring_ads), 'Chat count did not match reference SQL'
            report.update(chat='passed', chat_reference_parity='passed')
        except Exception as exc:
            report.update(chat='failed', chat_error=str(exc)[:1200])
    except Exception as exc:
        report.update(data='failed', data_error=str(exc)[:1200])
    print('HNJOB_RUNTIME_CHECK ' + json.dumps(report), flush=True)
    return report
