"""Parameterized queries over the complete post-level dataset."""
from backend import validate_namespace


def filtered(namespace, filters, include_dates=True):
    ns = validate_namespace(namespace)
    params = {k: filters.get(k, '') for k in ['start', 'end', 'country', 'policy', 'seniority']}
    conditions = ["p.status = 'success'", 'p.is_hiring = true',
        "(:country = '' OR array_contains(p.countries, :country))",
        "(:policy = '' OR array_contains(p.remote_policy, :policy))",
        "(:seniority = '' OR array_contains(p.seniority, :seniority))"]
    if include_dates:
        conditions.append('p.month BETWEEN :start AND :end')
    else:
        params.pop('start'); params.pop('end')
    return f'{ns}.post_attributes p WHERE ' + ' AND '.join(conditions), params


def query_for(name, ns, filters=None, **options):
    statement, params = _query_for(name, ns, filters, **options)
    return f'/* hnjob:{name} */\n' + statement, params


def _query_for(name, ns, filters=None, **options):
    ns = validate_namespace(ns)
    filters = filters or {}
    source, params = filtered(ns, filters)
    if name == 'metadata':
        return f"""SELECT count(*) AS total_posts, count(DISTINCT month) AS months,
          min(month) AS first_month, max(month) AS last_month,
          max(fetched_at) AS fetched_at, max(extracted_at) AS extracted_at,
          count_if(status = 'success' AND is_hiring) AS hiring_ads,
          count_if(status <> 'success') AS incomplete,
          count_if(NOT evidence_quotes_verified) AS evidence_flags,
          count_if(NOT salary_bounds_valid) AS salary_flags,
          count_if(country_review_status = 'needs_review') AS country_flags
          FROM {ns}.post_attributes""", {}
    if name == 'options':
        return f"""SELECT 'country' AS kind, country AS value FROM {ns}.post_countries GROUP BY country
          UNION ALL SELECT 'skill', skill FROM (SELECT skill, count(*) AS mentions
            FROM {ns}.post_skills GROUP BY skill ORDER BY mentions DESC, skill LIMIT 400)
          UNION ALL SELECT 'currency', currency FROM {ns}.post_salaries WHERE currency IS NOT NULL GROUP BY currency""", {}
    if name == 'coverage':
        return f"""SELECT c.*, i.threads, i.expected_comments, i.retrieved_comments,
          i.unavailable_comments, i.failed_comments, i.pending_comments, i.partial_month
          FROM {ns}.post_processing_coverage c LEFT JOIN {ns}.ingestion_coverage i USING (month)
          ORDER BY month""", {}
    if name == 'monthly':
        return f"""SELECT p.month, count(DISTINCT p.comment_id) AS advertisements,
          count_if(array_contains(p.remote_policy, 'remote')) AS remote_ads,
          count_if(size(p.salary) > 0) AS salary_ads
          FROM {source} GROUP BY p.month ORDER BY p.month""", params
    if name == 'skills':
        return f"""WITH ads AS (SELECT p.comment_id FROM {source})
          SELECT s.skill, count(DISTINCT s.comment_id) AS advertisements
          FROM {ns}.post_skills s JOIN ads a ON a.comment_id = s.comment_id
          GROUP BY s.skill ORDER BY advertisements DESC, s.skill LIMIT 30""", params
    if name == 'skill_trend':
        skills = options.get('skills', [])[:8]
        if not skills:
            raise ValueError('Choose at least one skill')
        names = []
        for i, skill in enumerate(skills):
            names.append(f':skill_{i}'); params[f'skill_{i}'] = skill
        return f"""WITH ads AS (SELECT p.comment_id, p.month FROM {source}), totals AS (
          SELECT month, count(DISTINCT comment_id) AS all_ads FROM ads GROUP BY month)
          SELECT a.month, s.skill, count(DISTINCT a.comment_id) AS advertisements,
          max(t.all_ads) AS all_ads, 100.0 * count(DISTINCT a.comment_id) / max(t.all_ads) AS share_pct
          FROM ads a JOIN {ns}.post_skills s ON a.comment_id = s.comment_id
          JOIN totals t ON a.month = t.month WHERE s.skill IN ({','.join(names)})
          GROUP BY a.month, s.skill ORDER BY a.month, s.skill""", params
    if name in {'policies', 'seniority', 'countries'}:
        column = {'policies': 'remote_policy', 'seniority': 'seniority', 'countries': 'countries'}[name]
        return f"""WITH ads AS (SELECT p.comment_id, p.{column} AS labels FROM {source})
          SELECT label, count(DISTINCT comment_id) AS advertisements
          FROM ads LATERAL VIEW explode(labels) e AS label
          GROUP BY label ORDER BY advertisements DESC, label LIMIT 20""", params
    if name == 'growth':
        source, params = filtered(ns, filters, include_dates=False)
        params.update({k: options[k] for k in ['prior_start', 'recent_start', 'recent_end', 'minimum']})
        return f"""WITH ads AS (SELECT p.comment_id,
            CASE WHEN p.month < :recent_start THEN 'previous' ELSE 'recent' END AS period
          FROM {source} AND p.month BETWEEN :prior_start AND :recent_end),
          totals AS (SELECT count_if(period = 'previous') AS previous_total,
            count_if(period = 'recent') AS recent_total FROM ads),
          mentions AS (SELECT s.skill,
            count(DISTINCT CASE WHEN a.period = 'previous' THEN a.comment_id END) AS previous_mentions,
            count(DISTINCT CASE WHEN a.period = 'recent' THEN a.comment_id END) AS recent_mentions
            FROM {ns}.post_skills s JOIN ads a ON a.comment_id = s.comment_id GROUP BY s.skill),
          shares AS (SELECT m.*, t.previous_total, t.recent_total,
            100.0 * previous_mentions / nullif(previous_total, 0) AS previous_share_pct,
            100.0 * recent_mentions / nullif(recent_total, 0) AS recent_share_pct
            FROM mentions m CROSS JOIN totals t
            WHERE previous_mentions >= :minimum AND recent_mentions >= :minimum)
          SELECT *, recent_share_pct - previous_share_pct AS growth_pp,
            100.0 * (recent_share_pct / nullif(previous_share_pct, 0) - 1) AS relative_growth_pct
          FROM shares ORDER BY growth_pp DESC, recent_mentions DESC, skill LIMIT 30""", params
    if name in {'salary_options', 'salaries'}:
        base = f"""WITH ads AS (SELECT p.comment_id FROM {source} AND p.salary_bounds_valid)
          SELECT s.* FROM {ns}.post_salaries s JOIN ads a ON s.comment_id = a.comment_id
          WHERE s.minimum > 0 AND s.maximum >= s.minimum"""
        if name == 'salary_options':
            return f"SELECT currency, period, type, count(*) AS ranges FROM ({base}) GROUP BY currency, period, type ORDER BY ranges DESC", params
        params.update({k: options[k] for k in ['currency', 'period', 'compensation_type']})
        return f"""SELECT *, (minimum + maximum) / 2.0 AS midpoint FROM ({base})
          WHERE currency = :currency AND period = :period AND type = :compensation_type
          ORDER BY month DESC, comment_id DESC LIMIT 2000""", params
    if name in {'explorer', 'explorer_count'}:
        params.update(term=options.get('term', ''), skill=options.get('skill', ''))
        source += f""" AND (:term = '' OR contains(lower(p.source_text), lower(:term)))
          AND (:skill = '' OR EXISTS (SELECT 1 FROM {ns}.post_skills s
            WHERE s.comment_id = p.comment_id AND s.skill = :skill))"""
        if name == 'explorer_count':
            return f'SELECT count(*) AS advertisements FROM {source}', params
        params['offset'] = max(0, int(options.get('page', 1)) - 1) * 20
        return f"""SELECT p.comment_id, p.company, p.month, p.source_url, p.source_text,
          p.skills, p.seniority, p.remote_policy, p.countries, p.country_scope, p.salary,
          p.evidence, p.evidence_quotes_verified, p.salary_bounds_valid, p.country_review_status
          FROM {source} ORDER BY p.posted_at DESC, p.comment_id DESC LIMIT 20 OFFSET :offset""", params
    raise ValueError(f'Unknown query: {name}')
