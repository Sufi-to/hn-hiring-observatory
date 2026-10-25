SELECT * FROM workspace.hnjob.model_benchmark_scores
ORDER BY complete_posts_passed DESC, field_checks_passed DESC,
         successful_outputs DESC, batch_seconds ASC;

SELECT * FROM workspace.hnjob.selected_extraction_model;

SELECT model, status, total_posts, successful_posts, failed_posts, pending_posts,
       started_at, updated_at, error
FROM workspace.hnjob.all_extraction_runs ORDER BY started_at DESC;

SELECT status, count(*) AS posts FROM workspace.hnjob.post_attributes GROUP BY status;

SELECT month, count(*) AS input_posts,
       count_if(status = 'success') AS processed_posts,
       count_if(status = 'success' AND is_hiring) AS hiring_ads,
       count_if(status <> 'success') AS incomplete_posts
FROM workspace.hnjob.post_attributes GROUP BY month ORDER BY month;

SELECT count(*) - count(DISTINCT comment_id) AS duplicate_post_ids
FROM workspace.hnjob.post_attributes;
