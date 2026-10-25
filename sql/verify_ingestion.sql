-- Run in the Free Edition SQL warehouse after ingestion.
SELECT coverage_status, count(*) AS months,
       sum(expected_comments) AS expected_comments,
       sum(retrieved_comments) AS retrieved_comments,
       sum(pending_comments) AS pending_comments,
       sum(failed_comments) AS failed_comments
FROM workspace.hnjob.ingestion_coverage GROUP BY coverage_status;

SELECT * FROM workspace.hnjob.ingestion_coverage ORDER BY month;

-- These checks must return zero.
SELECT count(*) - count(DISTINCT comment_id) AS duplicate_comments
FROM workspace.hnjob.raw_comments;

SELECT count(*) AS invalid_candidates
FROM workspace.hnjob.candidate_ads
WHERE parent_id <> thread_id OR deleted OR dead OR length(trim(text_clean)) = 0;

SELECT run_id, mode, status, started_at, finished_at, fetched_comments, error
FROM workspace.hnjob.ingestion_runs ORDER BY started_at DESC;
