-- Extracted fields, one record per source post.
SELECT test_rank, comment_id, company, skills, salary, seniority,
       remote_policy, countries, country_scope, status, source_url
FROM workspace.hnjob.test_first20_results
ORDER BY test_rank;

-- Source-reviewed functional checks, executed inside Databricks.
SELECT count(*) AS tested_posts,
       count_if(extraction_ok) AS extraction_passed,
       count_if(country_ok AND country_scope_ok) AS country_passed,
       count_if(remote_ok) AS remote_passed,
       count_if(seniority_ok) AS seniority_passed,
       count_if(size(missing_required_skills) = 0) AS skills_passed,
       count_if(salary_ok) AS salary_passed,
       count_if(evidence_quotes_ok) AS evidence_passed,
       count_if(all_checks_passed) AS all_checks_passed
FROM workspace.hnjob.test_first20_validation;

SELECT * FROM workspace.hnjob.test_first20_validation
WHERE NOT all_checks_passed ORDER BY test_rank;
