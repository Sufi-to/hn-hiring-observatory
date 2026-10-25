-- Compare Q3 2026 with Q2 2026; October is a partial month.
-- Rank by growth in the share of hiring posts mentioning a skill.
WITH posts AS (
  SELECT comment_id,
         CASE WHEN month < '2026-07' THEN 'previous' ELSE 'recent' END AS period
  FROM workspace.hnjob.post_attributes
  WHERE status = 'success'
    AND is_hiring = true
    AND month BETWEEN '2026-04' AND '2026-09'
), totals AS (
  SELECT count(DISTINCT CASE WHEN period = 'previous' THEN comment_id END) AS previous_total,
         count(DISTINCT CASE WHEN period = 'recent' THEN comment_id END) AS recent_total
  FROM posts
), mentions AS (
  SELECT s.skill,
         count(DISTINCT CASE WHEN p.period = 'previous' THEN p.comment_id END) AS previous_mentions,
         count(DISTINCT CASE WHEN p.period = 'recent' THEN p.comment_id END) AS recent_mentions
  FROM workspace.hnjob.post_skills s
  JOIN posts p ON p.comment_id = s.comment_id
  GROUP BY s.skill
), shares AS (
  SELECT m.*, t.previous_total, t.recent_total,
         100.0 * m.previous_mentions / nullif(t.previous_total, 0) AS previous_share_pct,
         100.0 * m.recent_mentions / nullif(t.recent_total, 0) AS recent_share_pct
  FROM mentions m CROSS JOIN totals t
  WHERE m.previous_mentions >= 20 AND m.recent_mentions >= 20
)
SELECT skill,
       previous_mentions, recent_mentions,
       previous_total, recent_total,
       round(previous_share_pct, 2) AS previous_share_pct,
       round(recent_share_pct, 2) AS recent_share_pct,
       round(recent_share_pct - previous_share_pct, 2) AS growth_percentage_points,
       round(100.0 * (recent_share_pct / nullif(previous_share_pct, 0) - 1), 1) AS relative_growth_pct
FROM shares
WHERE recent_share_pct > previous_share_pct
ORDER BY recent_share_pct - previous_share_pct DESC, recent_mentions DESC, skill
LIMIT 15;
