-- All available inputs must have exactly one current output.
SELECT count(*) AS posts, count(DISTINCT comment_id) AS distinct_posts,
       count_if(status = 'success') AS successful_posts,
       count_if(status <> 'success') AS incomplete_posts,
       count(DISTINCT model) AS selected_models,
       count(DISTINCT prompt_hash) AS prompt_versions,
       min(month) AS first_month, max(month) AS last_month,
       count(DISTINCT month) AS months
FROM workspace.hnjob.post_attributes;

SELECT count(*) AS missing_inputs
FROM workspace.hnjob.extraction_corpus c
LEFT ANTI JOIN workspace.hnjob.post_attributes p
ON c.comment_id = p.comment_id AND c.content_hash = p.content_hash;

SELECT count_if(is_hiring) AS ai_classified_hiring_posts,
       count_if(NOT is_hiring) AS ai_classified_non_hiring_posts,
       count_if(NOT evidence_quotes_verified) AS evidence_review_posts,
       count_if(NOT salary_bounds_valid) AS invalid_salary_posts,
       count_if(country_review_status = 'needs_review') AS country_review_posts
FROM workspace.hnjob.post_attributes WHERE status = 'success';

SELECT month, count(*) AS input_posts,
       count_if(status = 'success') AS processed_posts,
       count_if(status <> 'success') AS incomplete_posts
FROM workspace.hnjob.post_attributes GROUP BY month ORDER BY month;
