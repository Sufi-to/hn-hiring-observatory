"""Body appended to the shared extraction configuration by build_pipeline.py."""
import hashlib
import time
from datetime import datetime, timezone

PROMPT_HASH = hashlib.sha256((PROMPT + FORMAT).encode()).hexdigest()
MODELS = ["databricks-gpt-oss-20b", "databricks-qwen3-next-80b-a3b-instruct",
          "databricks-qwen35-122b-a10b", "databricks-meta-llama-3-3-70b-instruct",
          "databricks-gpt-oss-120b"]
BENCHMARK_ID = str(uuid.uuid4())
spark.sql(f"""CREATE TABLE IF NOT EXISTS {NS}.model_benchmark_attempts (
 benchmark_id STRING, model STRING, comment_id BIGINT, content_hash STRING,
 prompt_hash STRING, raw_output STRING, error STRING, created_at TIMESTAMP
) USING DELTA""")
spark.sql(f"""CREATE TABLE IF NOT EXISTS {NS}.model_benchmark_runs (
 benchmark_id STRING, model STRING, status STRING, batch_seconds DOUBLE,
 prompt_hash STRING, error STRING, created_at TIMESTAMP
) USING DELTA""")
for endpoint in MODELS:
    started = time.monotonic()
    status, error = "success", None
    try:
        spark.sql(f"""INSERT INTO {NS}.model_benchmark_attempts
          SELECT {literal(BENCHMARK_ID)}, {literal(endpoint)}, comment_id, content_hash,
                 {literal(PROMPT_HASH)}, ai.result, ai.errorMessage, current_timestamp()
          FROM (SELECT comment_id, content_hash,
            ai_query({literal(endpoint)}, concat({literal(PROMPT)}, text_clean),
              responseFormat => {literal(FORMAT)}, failOnError => false,
              modelParameters => named_struct('temperature', 0.0, 'max_tokens', 7000)) AS ai
            FROM {NS}.test_first20_inputs)""")
    except Exception as exc:
        status, error = "failed", str(exc)[:2000]
    seconds = time.monotonic() - started
    spark.createDataFrame([(BENCHMARK_ID, endpoint, status, seconds, PROMPT_HASH, error,
        datetime.now(timezone.utc).replace(tzinfo=None))], spark.table(f"{NS}.model_benchmark_runs").schema
    ).write.mode("append").saveAsTable(f"{NS}.model_benchmark_runs")
    print(json.dumps({"model": endpoint, "status": status, "seconds": seconds, "error": error}), flush=True)

# COMMAND ----------
spark.sql(f"""CREATE OR REPLACE VIEW {NS}.model_benchmark_parsed AS
 WITH attempts AS (
   SELECT *, from_json(raw_output, {literal(PARSED)}) AS data,
     row_number() OVER (PARTITION BY benchmark_id, model, comment_id ORDER BY created_at DESC) AS rn
   FROM {NS}.model_benchmark_attempts
 ) SELECT run.model, c.test_rank, c.comment_id, c.source_url, c.text_clean AS source_text,
   p.data.*, CASE WHEN p.error IS NULL AND p.data.is_hiring IS NOT NULL THEN 'success' ELSE 'error' END AS status
 FROM {NS}.model_benchmark_runs run CROSS JOIN {NS}.test_first20_inputs c
 LEFT JOIN attempts p ON p.benchmark_id = run.benchmark_id AND p.model = run.model
   AND p.comment_id = c.comment_id AND p.rn = 1
 WHERE run.benchmark_id = {literal(BENCHMARK_ID)}""")
spark.sql(BENCHMARK_CHECK_SQL)
spark.sql(f"""CREATE OR REPLACE TABLE {NS}.model_benchmark_scores USING DELTA AS
 SELECT c.model, count(*) AS tested_posts, count_if(extraction_ok) AS successful_outputs,
   count_if(country_ok AND country_scope_ok) AS country_passed,
   count_if(remote_ok) AS remote_passed, count_if(seniority_ok) AS seniority_passed,
   count_if(size(missing_required_skills) = 0) AS skills_passed,
   count_if(salary_ok) AS salary_passed, count_if(evidence_quotes_ok) AS evidence_passed,
   count_if(all_checks_passed) AS complete_posts_passed,
   count_if(country_ok AND country_scope_ok) + count_if(remote_ok) + count_if(seniority_ok)
     + count_if(size(missing_required_skills) = 0) + count_if(salary_ok) + count_if(evidence_quotes_ok) AS field_checks_passed,
   max(r.batch_seconds) AS batch_seconds, {literal(BENCHMARK_ID)} AS benchmark_id,
   {literal(PROMPT_HASH)} AS prompt_hash, current_timestamp() AS evaluated_at
 FROM {NS}.model_benchmark_checks c JOIN {NS}.model_benchmark_runs r
   ON c.model = r.model AND r.benchmark_id = {literal(BENCHMARK_ID)}
 GROUP BY c.model""")
scores = spark.sql(f"""SELECT * FROM {NS}.model_benchmark_scores
 ORDER BY complete_posts_passed DESC, field_checks_passed DESC,
 successful_outputs DESC, batch_seconds ASC, model""").collect()
assert len(scores) == len(MODELS), "Benchmark must account for every candidate model"
assert scores[0].successful_outputs == 20, "No model produced all 20 valid outputs"
assert scores[0].complete_posts_passed >= 15, "Best model needs further calibration before bulk processing"
winner = scores[0].model
spark.sql(f"""CREATE OR REPLACE TABLE {NS}.selected_extraction_model USING DELTA AS
 SELECT *, {literal(VERSION)} AS extraction_version FROM {NS}.model_benchmark_scores
 WHERE model = {literal(winner)}""")
dbutils.notebook.exit(json.dumps({"winner": winner, "scores": [r.asDict() for r in scores]}, default=str))
