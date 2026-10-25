import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'app'))
from backend import restricted_sql
from queries import query_for


class ReadOnlyAssistantTest(unittest.TestCase):
    def test_accepts_ctes_aggregations_and_array_filters(self):
        sql = """WITH ads AS (SELECT comment_id FROM workspace.hnjob.post_attributes
          WHERE status = 'success' AND array_contains(remote_policy, 'remote'))
          SELECT count(DISTINCT a.comment_id) AS ads FROM ads a
          JOIN workspace.hnjob.post_skills s ON a.comment_id = s.comment_id"""
        bounded = restricted_sql(sql)
        self.assertIn('LIMIT 200', bounded)
        self.assertIn('COUNT(DISTINCT', bounded)

    def test_rejects_mutations_external_sources_and_nested_injection(self):
        rejected = [
            'DROP TABLE workspace.hnjob.post_attributes',
            'SELECT * FROM workspace.hnjob.post_attributes; DELETE FROM workspace.hnjob.post_attributes',
            'SELECT * FROM system.billing.usage',
            'SELECT * FROM workspace.hnjob.advertisements',
            'SELECT * FROM post_attributes',
            "SELECT http_request('secret', 'GET') FROM workspace.hnjob.post_attributes",
            "SELECT ai_query('model','prompt') FROM workspace.hnjob.post_attributes",
            "SELECT * FROM read_files('/tmp/data')",
            'WITH hidden AS (SELECT * FROM system.billing.usage) SELECT * FROM hidden',
            'SELECT other.catalog.count(*) FROM workspace.hnjob.post_attributes',
            'SELECT 42',
        ]
        for sql in rejected:
            with self.subTest(sql=sql), self.assertRaises(ValueError):
                restricted_sql(sql)

    def test_search_values_are_bound_and_namespace_cannot_be_injected(self):
        attack = "' OR 1=1 --"
        statement, params = query_for('explorer', 'workspace.hnjob',
            {'start': '2026-01', 'end': '2026-09'}, term=attack, page=2)
        self.assertNotIn(attack, statement)
        self.assertEqual(params['term'], attack)
        self.assertEqual(params['offset'], 20)
        with self.assertRaises(ValueError): query_for('metadata', 'workspace.hnjob; DROP TABLE x')

    def test_salary_queries_keep_types_and_validity_separate(self):
        statement, params = query_for('salaries', 'workspace.hnjob',
            {'start': '2020-01', 'end': '2026-09'}, currency='EUR', period='annual', compensation_type='base')
        self.assertIn('salary_bounds_valid', statement)
        self.assertEqual(params['currency'], 'EUR')
        self.assertEqual(params['compensation_type'], 'base')


if __name__ == '__main__': unittest.main()
