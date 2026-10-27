"""Execute the recommendation SQL against adversarial small datasets."""
import json
import sqlite3
import sys
from pathlib import Path
import unittest
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'app'))
from queries import query_for
from next_skill import comparison_periods, is_stale


class RecommendationTest(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(':memory:')
        self.db.create_function('array_contains', 2, lambda a, x: x in json.loads(a))
        self.db.execute('CREATE TABLE post_attributes (comment_id INT, month TEXT, status TEXT, is_hiring BOOL, countries TEXT, remote_policy TEXT, seniority TEXT, company TEXT, posted_at TEXT, source_url TEXT, source_text TEXT, evidence_quotes_verified BOOL, country_review_status TEXT)')
        self.db.execute('CREATE TABLE post_skills (comment_id INT, skill TEXT)')
        for i in range(1, 45):
            recent = i <= 24
            self.db.execute('INSERT INTO post_attributes VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)',
                (i, '2026-09' if recent else '2026-06', 'success', True, '["Canada"]', '["remote"]', '["senior"]', 'Example', str(i).zfill(3), f'https://news.ycombinator.com/item?id={i}', 'source', True, 'reviewed'))
            skills = ['python', 'sql'] + (['docker', 'rust'] if i <= 6 else []) + (['rare'] if i <= 4 else [])
            for skill in skills * 2: # duplicates must not increase counts or evidence rows
                self.db.execute('INSERT INTO post_skills VALUES (?,?)', (i, skill))
        self.args = dict(skills=['python', 'sql'], prior_start='2026-04', recent_start='2026-07', recent_end='2026-09')

    def run_query(self, name='next_skills', filters=None, **kwargs):
        sql, params = query_for(name, 'workspace.hnjob', filters or {}, **{**self.args, **kwargs})
        return pd.read_sql_query(sql.replace('workspace.hnjob.', ''), self.db, params=params)

    def test_distinct_counts_ties_selected_exclusion_and_zero_baseline(self):
        rows = self.run_query()
        self.assertEqual(rows.skill.tolist(), ['docker', 'rust'])
        self.assertEqual(rows.recent_total.tolist(), [24, 24])
        self.assertEqual(rows.recent_mentions.tolist(), [6, 6])
        self.assertEqual(rows.recent_share_pct.tolist(), [25, 25])
        self.assertEqual(rows.previous_share_pct.tolist(), [0, 0])
        self.assertEqual(rows.alongside_0.tolist(), [1, 1])

    def test_filter_and_minimum_cohort(self):
        rows = self.run_query(filters={'country': 'France'})
        self.assertEqual(rows.recent_total.iloc[0], 0)
        self.assertTrue(pd.isna(rows.skill.iloc[0]))
        self.db.execute('DELETE FROM post_attributes WHERE comment_id BETWEEN 19 AND 24')
        self.assertTrue(pd.isna(self.run_query().skill.iloc[0]))
        self.assertTrue(pd.isna(self.run_query(filters={'policy': 'onsite'}).skill.iloc[0]))
        self.assertTrue(pd.isna(self.run_query(filters={'seniority': 'junior'}).skill.iloc[0]))

    def test_evidence_exact_cohort_unique_and_bounded(self):
        rows = self.run_query('next_skill_evidence', candidates=['docker', 'rust'])
        self.assertEqual(len(rows), 6)
        self.assertEqual(rows[rows.skill == 'docker'].comment_id.tolist(), [6, 5, 4])
        self.assertEqual(rows.duplicated(['skill', 'comment_id']).sum(), 0)
        self.assertTrue(self.run_query('next_skill_evidence', filters={'country': 'France'}, candidates=['docker']).empty)

    def test_small_prior_unknown_and_bound_parameters(self):
        self.db.execute('DELETE FROM post_attributes WHERE comment_id = 44')
        self.assertTrue(self.run_query().previous_share_pct.isna().all())
        attack = "x' OR 1=1 --"
        sql, params = query_for('next_skills', 'workspace.hnjob', {}, **{**self.args, 'skills':[attack]})
        self.assertNotIn(attack, sql)
        self.assertIn(attack, params.values())
        for skills in [[], ['a','b','c','d','e','f']]:
            with self.assertRaises(ValueError): self.run_query(skills=skills)


class CoverageTest(unittest.TestCase):
    def frame(self):
        return pd.DataFrame([dict(month=str(m), incomplete_posts=0, failed_comments=0,
            pending_comments=0, partial_month=False, processed_posts=10, input_posts=10,
            retrieved_comments=11, expected_comments=11) for m in pd.period_range('2026-04','2026-09',freq='M')])

    def test_periods_and_blocked_recent_without_fallback(self):
        frame = self.frame()
        periods = comparison_periods(frame, '2026-10-27')
        self.assertTrue(periods['recent_complete'])
        self.assertTrue(periods['prior_complete'])
        self.assertEqual(periods['recent_start'], '2026-07')
        for column, value in [('failed_comments', 1), ('pending_comments', 1), ('incomplete_posts', 1), ('partial_month', True), ('processed_posts', 9), ('retrieved_comments', 10)]:
            changed = frame.copy(); changed.loc[5, column] = value
            self.assertFalse(comparison_periods(changed, '2026-10-27')['recent_complete'], column)
        self.assertFalse(comparison_periods(frame.iloc[:-1], '2026-10-27')['recent_complete'])
        self.assertFalse(comparison_periods(frame.iloc[1:], '2026-10-27')['prior_complete'])

    def test_staleness(self):
        self.assertFalse(is_stale('2026-10-25', '2026-10-27T00:00Z'))
        self.assertTrue(is_stale('2026-10-01', '2026-10-27T00:00Z'))
        self.assertTrue(is_stale(None))


if __name__ == '__main__': unittest.main()

# Exercise the actual Streamlit workflow with deterministic service responses.
from unittest.mock import patch
import streamlit as st
from streamlit.testing.v1 import AppTest
from backend import QueryResult
from test_app import FakeWarehouse


class NextWarehouse(FakeWarehouse):
    fail = False
    sparse = False
    def query(self, statement, parameters=None, **kwargs):
        if 'hnjob:next_skills' in statement:
            if self.fail: raise RuntimeError('sensitive internal service detail')
            return QueryResult(pd.DataFrame([dict(skill='docker' if not self.sparse else None,
                recent_total=24 if not self.sparse else 3, previous_total=20,
                recent_mentions=6, previous_mentions=0, recent_share_pct=25,
                previous_share_pct=0, alongside_0=1)]), 'recommendation-test')
        if 'hnjob:next_skill_evidence' in statement:
            return QueryResult(pd.DataFrame([dict(skill='docker', comment_id=i, company='Example',
                month='2026-09', source_url=f'https://news.ycombinator.com/item?id={i}',
                source_text='python docker', evidence_quotes_verified=True, country_review_status='reviewed')
                for i in range(1,4)]), 'evidence-test')
        return super().query(statement, parameters, **kwargs)


class NextSkillUITest(unittest.TestCase):
    def setUp(self):
        st.cache_data.clear(); st.cache_resource.clear()

    def launch(self):
        app = AppTest.from_file(str(Path(__file__).resolve().parents[1]/'app/app.py'), default_timeout=30).run()
        app.radio[0].set_value('Your Next Skill').run()
        return app

    def submit(self, app):
        app.multiselect[0].set_value(['python']).run()
        [b for b in app.button if b.label == 'Find adjacent skills'][0].click().run()

    def test_results_sql_download_and_selection_survive_navigation(self):
        with patch('backend.Warehouse', return_value=NextWarehouse()), patch('next_skill_ui.comparison_periods', side_effect=lambda frame: comparison_periods(frame,'2026-10-27')):
            app=self.launch()
            self.submit(app)
            self.assertFalse(app.exception)
            self.assertTrue(any(s.value=='docker' for s in app.subheader))
            self.assertEqual(len(app.get('download_button')), 1)
            self.assertTrue(any('WITH cohort' in c.value for c in app.code))
            app.radio[0].set_value('Overview').run()
            app.radio[0].set_value('Your Next Skill').run()
            self.assertEqual(app.multiselect[0].value, ['python'])
            self.assertTrue(any(s.value=='docker' for s in app.subheader))
            [s for s in app.selectbox if s.label=='Work policy'][0].set_value('remote').run()
            self.assertFalse(any(s.value=='docker' for s in app.subheader))

    def test_empty_selection_sparse_results_and_safe_retry(self):
        service=NextWarehouse()
        with patch('backend.Warehouse', return_value=service), patch('next_skill_ui.comparison_periods', side_effect=lambda frame: comparison_periods(frame,'2026-10-27')):
            app=self.launch()
            [b for b in app.button if b.label=='Find adjacent skills'][0].click().run()
            self.assertTrue(any('Choose at least' in i.value for i in app.info))
            service.fail=True
            self.submit(app)
            self.assertFalse(app.exception)
            self.assertTrue(app.error)
            self.assertFalse(any('sensitive internal' in c.value for c in app.caption))
            service.fail=False; service.sparse=True
            [b for b in app.button if b.label=='Retry data connection'][0].click().run()
            self.assertTrue(any('Not enough data' in i.value for i in app.info))

    def test_missing_coverage_blocks_query_and_staleness_visible(self):
        with patch('backend.Warehouse', return_value=NextWarehouse()), patch('next_skill_ui.is_stale', return_value=True), patch('next_skill_ui.comparison_periods', side_effect=lambda frame: comparison_periods(frame,'2026-11-27')):
            app=self.launch()
            self.assertFalse(app.exception)
            self.assertTrue(any('seven days' in w.value for w in app.warning))
            self.assertTrue(any('Recommendations are unavailable' in w.value for w in app.warning))
            self.assertFalse(app.multiselect)
