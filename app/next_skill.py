"""Deterministic adjacent-skill recommendations and their coverage contract."""
from datetime import date
import pandas as pd


def comparison_periods(coverage, today=None):
    """Never skip a broken recent month to make an older ranking look current."""
    end = pd.Period(today or date.today(), freq='M') - 1
    recent = [str(end - i) for i in (2, 1, 0)]
    prior = [str(end - i) for i in (5, 4, 3)]

    def complete(months):
        rows = coverage[coverage.month.isin(months)]
        if len(rows) != 3 or rows.month.nunique() != 3:
            return False
        for col in ['incomplete_posts', 'failed_comments', 'pending_comments']:
            if col not in rows or rows[col].isna().any() or rows[col].ne(0).any():
                return False
        if rows.partial_month.isna().any() or rows.partial_month.any():
            return False
        return bool((rows.processed_posts == rows.input_posts).all() and
                    (rows.retrieved_comments == rows.expected_comments).all())

    return dict(recent_start=recent[0], recent_end=recent[-1], prior_start=prior[0],
                prior_end=prior[-1], recent_complete=complete(recent), prior_complete=complete(prior))


def is_stale(value, now=None):
    stamp = pd.to_datetime(value, utc=True, errors='coerce')
    return pd.isna(stamp) or (pd.Timestamp(now or pd.Timestamp.now(tz='UTC')) - stamp).total_seconds() > 7 * 86400


def recommendation_query(name, ns, source, params, options):
    selected = sorted(set(options.get('skills', [])))
    if not 1 <= len(selected) <= 5 or any(not isinstance(s, str) or not s for s in selected):
        raise ValueError('Choose one to five normalized skills')
    params.update({k: options[k] for k in ['prior_start', 'recent_start', 'recent_end']})
    names = []
    flags = []
    for i, skill in enumerate(selected):
        key = f'selected_{i}'
        names.append(':' + key)
        params[key] = skill
        flags.append(f"CASE WHEN EXISTS (SELECT 1 FROM {ns}.post_skills x WHERE x.comment_id = p.comment_id AND x.skill = :{key}) THEN 1 ELSE 0 END AS has_{i}")
    cohort = f"""WITH cohort AS (
      SELECT DISTINCT p.comment_id, p.month, {', '.join(flags)} FROM {source}
      AND p.month BETWEEN :prior_start AND :recent_end
      AND EXISTS (SELECT 1 FROM {ns}.post_skills s WHERE s.comment_id = p.comment_id
        AND s.skill IN ({','.join(names)})))"""
    if name == 'next_skill_evidence':
        candidates = options.get('candidates', [])
        if not 1 <= len(candidates) <= 3:
            raise ValueError('Choose one to three suggested skills')
        placeholders = []
        for i, skill in enumerate(candidates):
            params[f'candidate_{i}'] = skill
            placeholders.append(f':candidate_{i}')
        return cohort + f""", evidence AS (
          SELECT DISTINCT s.skill, p.comment_id, p.company, p.month, p.posted_at,
            p.source_url, p.source_text, p.evidence_quotes_verified, p.country_review_status
          FROM cohort a JOIN {ns}.post_skills s ON a.comment_id = s.comment_id
          JOIN {ns}.post_attributes p ON p.comment_id = a.comment_id
          WHERE a.month >= :recent_start AND s.skill IN ({','.join(placeholders)})),
          numbered AS (SELECT *, row_number() OVER (
            PARTITION BY skill ORDER BY posted_at DESC, comment_id DESC) AS position FROM evidence)
          SELECT * FROM numbered WHERE position <= 3 ORDER BY skill, position""", params
    pairs = ', '.join(f"max(CASE WHEN a.month >= :recent_start THEN a.has_{i} ELSE 0 END) AS alongside_{i}" for i in range(len(selected)))
    return cohort + f""", totals AS (
      SELECT count(DISTINCT CASE WHEN month >= :recent_start THEN comment_id END) AS recent_total,
        count(DISTINCT CASE WHEN month < :recent_start THEN comment_id END) AS previous_total FROM cohort),
      mentions AS (
        SELECT s.skill,
          count(DISTINCT CASE WHEN a.month >= :recent_start THEN a.comment_id END) AS recent_mentions,
          count(DISTINCT CASE WHEN a.month < :recent_start THEN a.comment_id END) AS previous_mentions,
          {pairs}
        FROM cohort a JOIN {ns}.post_skills s ON a.comment_id = s.comment_id
        WHERE s.skill NOT IN ({','.join(names)}) GROUP BY s.skill),
      ranked AS (SELECT * FROM mentions WHERE recent_mentions >= 5
        ORDER BY recent_mentions DESC, skill LIMIT 3)
      SELECT r.*, t.recent_total, t.previous_total,
        100.0 * r.recent_mentions / nullif(t.recent_total, 0) AS recent_share_pct,
        CASE WHEN t.previous_total >= 20 THEN
          100.0 * r.previous_mentions / t.previous_total END AS previous_share_pct
      FROM totals t LEFT JOIN ranked r ON t.recent_total >= 20
      ORDER BY r.recent_mentions DESC, r.skill""", params
