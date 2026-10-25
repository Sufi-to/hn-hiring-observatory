"""UI flows with small fixtures; live SQL is verified separately."""
from pathlib import Path
import re
import sys
import threading
import unittest
from unittest.mock import patch
import pandas as pd
import streamlit as st
from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'app'))
from backend import QueryResult


class FakeWarehouse:
    namespace = 'workspace.hnjob'
    calls = []

    def query(self, statement, parameters=None, **kwargs):
        self.calls.append((statement, parameters or {}))
        match = re.search(r'hnjob:(\w+)', statement)
        name = match.group(1) if match else 'chat_result'
        frames = {
            'metadata': [dict(total_posts=40065, months=82, first_month='2020-01', last_month='2026-10',
                fetched_at='2026-10-25 00:00', extracted_at='2026-10-25 01:00', hiring_ads=39596,
                incomplete=0, evidence_flags=153, salary_flags=4, country_flags=30)],
            'options': [dict(kind='skill', value=s) for s in ['python', 'rust', 'typescript']] +
                [dict(kind='country', value='United Kingdom'), dict(kind='currency', value='EUR')],
            'coverage': [dict(month=str(m), input_posts=10, processed_posts=10, hiring_ads=9,
                non_hiring_posts=1, incomplete_posts=0, evidence_review_posts=0, threads=1,
                expected_comments=11, retrieved_comments=11, unavailable_comments=1,
                failed_comments=0, pending_comments=0, partial_month=str(m)=='2026-10')
                for m in pd.period_range('2020-01', '2026-10', freq='M')],
            'monthly': [dict(month='2026-08', advertisements=10, remote_ads=5, salary_ads=2),
                        dict(month='2026-09', advertisements=12, remote_ads=8, salary_ads=3)],
            'skills': [dict(skill='python', advertisements=8), dict(skill='rust', advertisements=5)],
            'policies': [dict(label='remote', advertisements=12), dict(label='unspecified', advertisements=10)],
            'seniority': [dict(label='senior', advertisements=15)],
            'countries': [dict(label='United Kingdom', advertisements=10)],
            'skill_trend': [dict(month='2026-09', skill='python', advertisements=8, all_ads=12, share_pct=66.7)],
            'growth': [dict(skill='python', previous_total=50, recent_total=40,
                previous_mentions=20, recent_mentions=24, previous_share_pct=40,
                recent_share_pct=60, growth_pp=20, relative_growth_pct=50)],
            'salary_options': [dict(currency='EUR', period='annual', type='base', ranges=2)],
            'salaries': [dict(comment_id=1, company='Example', month='2026-09', title='Engineer',
                minimum=60000, maximum=90000, midpoint=75000, original_text='EUR 60-90k annual base',
                source_url='https://news.ycombinator.com/item?id=1')],
            'explorer_count': [dict(advertisements=1)],
            'explorer': [dict(comment_id=1, company='Example', month='2026-09',
                source_url='https://news.ycombinator.com/item?id=1', source_text='Python | REMOTE',
                skills=['python'], seniority=['senior'], remote_policy=['remote'],
                countries=[], country_scope=['worldwide'], salary=[], evidence={'remote': ['REMOTE']},
                evidence_quotes_verified=True, salary_bounds_valid=True, country_review_status='not_needed')],
            'chat_result': [dict(month='2026-08', advertisements=10), dict(month='2026-09', advertisements=12)],
        }
        return QueryResult(pd.DataFrame(frames[name]), 'test-statement')

    def plan_answer(self, question, filters, history):
        return dict(sql='SELECT month, count(*) AS advertisements FROM workspace.hnjob.post_attributes GROUP BY month',
                    summary='Counts of hiring advertisements by month.', clarification=None)


class AppFlowTest(unittest.TestCase):
    def setUp(self):
        st.cache_data.clear(); st.cache_resource.clear(); FakeWarehouse.calls = []

    def launch(self):
        return AppTest.from_file(str(ROOT / 'app/app.py'), default_timeout=30).run()

    def test_all_screens_render_and_filters_bind(self):
        with patch('backend.Warehouse', return_value=FakeWarehouse()):
            app = self.launch()
            self.assertEqual(len(app.exception), 0, str(app.exception))
            self.assertGreater(len(app.get('plotly_chart')), 0)
            for page in ['Skills', 'Compensation', 'Explore ads', 'Data coverage']:
                app.radio[0].set_value(page).run()
                self.assertEqual(len(app.exception), 0, f'{page}: {app.exception}')
            app.radio[0].set_value('Explore ads').run()
            attack = "' OR 1=1 --"
            app.text_input[0].set_value(attack)
            app.button(key='FormSubmitter:searchform-Search advertisements').click().run()
            searches = [(s,p) for s,p in FakeWarehouse.calls if p.get('term') == attack]
            self.assertTrue(searches)
            self.assertNotIn(attack, searches[-1][0])

    def test_chat_shows_sql_results_and_can_clear(self):
        with patch('backend.Warehouse', return_value=FakeWarehouse()):
            app = self.launch()
            app.radio[0].set_value('Ask the data').run()
            app.chat_input[0].set_value('How many hiring ads per month?').run()
            self.assertEqual(len(app.exception), 0, str(app.exception))
            self.assertTrue(any('SELECT month' in c.value for c in app.code))
            self.assertGreater(len(app.dataframe), 0)
            self.assertEqual(len(app.session_state['chat_history']), 2)
            [b for b in app.button if b.label == 'New conversation'][0].click().run()
            self.assertEqual(app.session_state['chat_history'], [])

    def test_unavailable_service_is_a_recoverable_screen(self):
        with patch('backend.Warehouse', side_effect=RuntimeError('warehouse unavailable')):
            app = self.launch()
            self.assertEqual(len(app.exception), 0)
            self.assertTrue(any('Connect to the Databricks dataset' in v.value for v in app.info))

    def test_cache_stores_data_instead_of_result_runtime_state(self):
        class RuntimeWarehouse(FakeWarehouse):
            def query(self, *args, **kwargs):
                result = super().query(*args, **kwargs)
                result.runtime_lock = threading.Lock()
                return result

        with patch('backend.Warehouse', return_value=RuntimeWarehouse()):
            app = self.launch()
            self.assertEqual(len(app.exception), 0, str(app.exception))
            self.assertEqual(len(app.error), 0, str(app.error))
            self.assertGreater(len(app.get('plotly_chart')), 0)
            app.run()
            self.assertEqual(len(app.error), 0, str(app.error))


if __name__ == '__main__': unittest.main()
