"""Apply the benchmark winner to the corpus, checkpointing large yearly groups."""
import hashlib
from datetime import datetime, timezone
from delta.tables import DeltaTable

PROMPT_HASH = hashlib.sha256((PROMPT + FORMAT).encode()).hexdigest()
selection = spark.table(f"{NS}.selected_extraction_model").first()
assert selection and selection.prompt_hash == PROMPT_HASH, "Selection must match this exact prompt and schema"
MODEL = selection.model
RUN_ID = str(uuid.uuid4())
spark.sql(f"""CREATE OR REPLACE TABLE {NS}.extraction_corpus USING DELTA AS
 SELECT * FROM {NS}.candidate_ads""")
spark.sql(f"""CREATE TABLE IF NOT EXISTS {NS}.all_post_attempts (
 attempt_id STRING, run_id STRING, comment_id BIGINT, content_hash STRING,
 model STRING, prompt_hash STRING, extraction_version STRING,
 raw_output STRING, error STRING, created_at TIMESTAMP
) USING DELTA""")
spark.sql(f"""CREATE TABLE IF NOT EXISTS {NS}.corpus_country_reviews (
 attempt_id STRING, run_id STRING, comment_id BIGINT, content_hash STRING,
 model STRING, prompt_hash STRING, review_version STRING,
 raw_output STRING, error STRING, created_at TIMESTAMP
) USING DELTA""")
spark.sql(f"""CREATE TABLE IF NOT EXISTS {NS}.all_extraction_runs (
 run_id STRING, model STRING, prompt_hash STRING, status STRING,
 total_posts BIGINT, successful_posts BIGINT, failed_posts BIGINT, pending_posts BIGINT,
 started_at TIMESTAMP, updated_at TIMESTAMP, error STRING
) USING DELTA""")
TOTAL = spark.table(f"{NS}.extraction_corpus").count()
STARTED = datetime.now(timezone.utc).replace(tzinfo=None)


def valid(alias="a"):
    return f"""{alias}.error IS NULL AND {alias}.data.is_hiring IS NOT NULL
      AND {alias}.data.skills IS NOT NULL AND {alias}.data.salary IS NOT NULL
      AND {alias}.data.countries IS NOT NULL AND {alias}.data.evidence IS NOT NULL
      AND {alias}.data.seniority IS NOT NULL AND {alias}.data.remote_policy IS NOT NULL
      AND {alias}.data.country_scope IS NOT NULL
      AND (NOT {alias}.data.is_hiring OR
        (size({alias}.data.seniority) > 0 AND size({alias}.data.remote_policy) > 0
         AND size({alias}.data.country_scope) > 0))"""


BASE = f"""SELECT *, from_json(raw_output, {literal(PARSED)}) AS data
 FROM {NS}.all_post_attempts WHERE model = {literal(MODEL)}
 AND prompt_hash = {literal(PROMPT_HASH)}"""


def publish():
    spark.sql(f"""CREATE OR REPLACE TABLE {NS}.post_attributes USING DELTA AS
      WITH parsed AS ({BASE}), ranked AS (
       SELECT a.*, row_number() OVER (PARTITION BY comment_id, content_hash
         ORDER BY CASE WHEN {valid('a')} THEN 0 ELSE 1 END, created_at DESC, attempt_id DESC) AS rn
       FROM parsed a
      ), reviews AS (
       SELECT *, from_json(raw_output, 'STRUCT<countries:ARRAY<STRING>,evidence:ARRAY<STRING>>') AS data,
         row_number() OVER (PARTITION BY comment_id, content_hash ORDER BY created_at DESC) AS rn
       FROM {NS}.corpus_country_reviews WHERE model = {literal(MODEL)}
         AND prompt_hash = {literal(PROMPT_HASH)} AND review_version = {literal(COUNTRY_VERSION)}
         AND error IS NULL
      ), checked AS (
       SELECT r.* FROM reviews r JOIN {NS}.extraction_corpus c
         ON r.comment_id = c.comment_id AND r.content_hash = c.content_hash
       WHERE r.rn = 1 AND size(r.data.countries) > 0 AND size(r.data.evidence) > 0
         AND forall(r.data.evidence, quote -> length(quote) > 0 AND contains(split(c.text_clean, '\\n')[0], quote))
      ) SELECT c.comment_id, c.thread_id, c.month, c.posted_at, c.source_url,
       c.text_clean AS source_text, c.content_hash, c.fetched_at,
       {literal(MODEL)} AS model, {literal(PROMPT_HASH)} AS prompt_hash,
       {literal(VERSION)} AS extraction_version,
       a.data.company AS company, a.data.is_hiring AS is_hiring,
       array_distinct(a.data.skills) AS skills,
       transform(a.data.salary, s -> named_struct('title', s.title, 'minimum', s.minimum,
         'maximum', s.maximum, 'currency', s.currency, 'period', s.period,
         'type', CASE WHEN s.type = 'base' AND NOT lower(s.original_text) RLIKE
            '(^|[^a-z])base([^a-z]|$)|basic salary' THEN 'unspecified' ELSE s.type END,
         'original_text', s.original_text)) AS salary,
       CASE WHEN a.data.is_hiring AND lower(split(c.text_clean, '\\n')[0]) RLIKE
         '(^|[^a-z])(engineer(ing)? manager|head of|director|chief engineer|front.?end manager)([^a-z]|$)'
         THEN array_union(array_except(a.data.seniority, array('unspecified')), array('leadership'))
         ELSE array_distinct(a.data.seniority) END AS seniority,
       array_distinct(a.data.remote_policy) AS remote_policy,
       coalesce(r.data.countries, a.data.countries) AS countries,
       a.data.country_scope AS country_scope,
       CASE WHEN a.data.remote_policy = array('onsite')
         AND lower(split(c.text_clean, '\\n')[0]) RLIKE 'on.?site'
         AND exists(a.data.evidence.country, quote -> NOT contains(split(c.text_clean, '\\n')[0], quote))
         THEN CASE WHEN r.comment_id IS NOT NULL THEN 'reviewed' ELSE 'needs_review' END
         ELSE 'not_needed' END AS country_review_status,
       forall(a.data.salary, s -> (s.minimum IS NULL OR s.minimum >= 0)
         AND (s.maximum IS NULL OR s.maximum >= 0)
         AND (s.minimum IS NULL OR s.maximum IS NULL OR s.minimum <= s.maximum)) AS salary_bounds_valid,
       named_struct('country', coalesce(r.data.evidence, a.data.evidence.country),
         'remote', a.data.evidence.remote, 'salary', a.data.evidence.salary) AS evidence,
       a.raw_output, a.error, a.created_at AS extracted_at,
       r.raw_output AS country_review_output,
       CASE WHEN a.comment_id IS NULL THEN 'pending'
         WHEN {valid('a')} THEN 'success'
         WHEN a.error IS NOT NULL THEN 'provider_error' ELSE 'invalid_output' END AS status,
       CASE WHEN {valid('a')} THEN
         forall(concat(coalesce(r.data.evidence, a.data.evidence.country), a.data.evidence.remote,
           a.data.evidence.salary), quote -> length(quote) > 0 AND contains(c.text_clean, quote))
         ELSE false END AS evidence_quotes_verified
      FROM {NS}.extraction_corpus c LEFT JOIN ranked a
       ON c.comment_id = a.comment_id AND c.content_hash = a.content_hash AND a.rn = 1
      LEFT JOIN checked r ON c.comment_id = r.comment_id AND c.content_hash = r.content_hash""")
    return spark.sql(f"""SELECT count_if(status = 'success') AS successful,
       count_if(status IN ('provider_error', 'invalid_output')) AS failed,
       count_if(status = 'pending') AS pending FROM {NS}.post_attributes""").first()


def log(status, counts, error=None):
    row = (RUN_ID, MODEL, PROMPT_HASH, status, TOTAL, counts.successful, counts.failed,
           counts.pending, STARTED, datetime.now(timezone.utc).replace(tzinfo=None), error)
    frame = spark.createDataFrame([row], spark.table(f"{NS}.all_extraction_runs").schema)
    DeltaTable.forName(spark, f"{NS}.all_extraction_runs").alias("t").merge(
        frame.alias("s"), "t.run_id = s.run_id"
    ).whenMatchedUpdateAll().whenNotMatchedInsertAll().execute()


# Seed the selected model's benchmark outputs; these exact posts need no repeat inference.
spark.sql(f"""INSERT INTO {NS}.all_post_attempts
 SELECT uuid(), {literal(RUN_ID)}, b.comment_id, b.content_hash, b.model, b.prompt_hash,
   {literal(VERSION)}, b.raw_output, b.error, b.created_at
 FROM {NS}.model_benchmark_attempts b JOIN {NS}.extraction_corpus c
   ON b.comment_id = c.comment_id AND b.content_hash = c.content_hash
 LEFT ANTI JOIN {NS}.all_post_attempts existing ON existing.comment_id = b.comment_id
   AND existing.content_hash = b.content_hash AND existing.model = b.model AND existing.prompt_hash = b.prompt_hash
 WHERE b.benchmark_id = {literal(selection.benchmark_id)} AND b.model = {literal(MODEL)}
   AND b.prompt_hash = {literal(PROMPT_HASH)} AND b.error IS NULL""")
counts = publish()
log("running", counts)
years = [r.year for r in spark.sql(f"SELECT DISTINCT substr(month, 1, 4) AS year FROM {NS}.extraction_corpus ORDER BY year").collect()]
try:
    for year in years:
        for retry in range(3):
            pending_sql = f"""SELECT c.comment_id, c.content_hash, c.text_clean
             FROM {NS}.extraction_corpus c LEFT ANTI JOIN ({BASE}) a
              ON c.comment_id = a.comment_id AND c.content_hash = a.content_hash AND ({valid('a')})
             WHERE substr(c.month, 1, 4) = {literal(year)}"""
            if spark.sql(pending_sql).limit(1).count() == 0:
                break
            # Large year groups let native AI Functions parallelize and scale;
            # each completed group is a durable checkpoint on Free Edition.
            batch_id = str(uuid.uuid4())
            spark.sql(f"""INSERT INTO {NS}.all_post_attempts
             SELECT concat({literal(batch_id)}, '-', cast(comment_id AS STRING)), {literal(RUN_ID)},
               comment_id, content_hash, {literal(MODEL)}, {literal(PROMPT_HASH)}, {literal(VERSION)},
               ai.result, ai.errorMessage, current_timestamp()
             FROM (SELECT comment_id, content_hash,
               ai_query({literal(MODEL)}, concat({literal(PROMPT)}, text_clean),
                 responseFormat => {literal(FORMAT)}, failOnError => false,
                 modelParameters => named_struct('temperature', 0.0, 'max_tokens', {7000 if retry == 0 else 12000})) AS ai
               FROM ({pending_sql}))""")
            counts = publish()
            log("running", counts)
            print(json.dumps({"year": year, "retry": retry, "successful": counts.successful,
                              "failed": counts.failed, "pending": counts.pending}), flush=True)
            quota_errors = spark.sql(f"""SELECT count(*) AS n FROM {NS}.all_post_attempts
             WHERE attempt_id LIKE {literal(batch_id + '%')} AND lower(coalesce(error, '')) RLIKE
             'quota|fair.?usage|resource_exhausted|spend.?limit|budget.?limit'""").first().n
            if quota_errors:
                raise RuntimeError(f"Databricks quota or budget limit reported for {quota_errors} rows; successes saved, rerun after reset")

        spark.sql(f"""INSERT INTO {NS}.corpus_country_reviews
         SELECT uuid(), {literal(RUN_ID)}, comment_id, content_hash, {literal(MODEL)},
           {literal(PROMPT_HASH)}, {literal(COUNTRY_VERSION)}, ai.result, ai.errorMessage, current_timestamp()
         FROM (SELECT p.comment_id, p.content_hash,
           ai_query({literal(MODEL)}, concat({literal(COUNTRY_PROMPT)}, split(p.source_text, '\\n')[0]),
             responseFormat => {literal(COUNTRY_FORMAT)}, failOnError => false,
             modelParameters => named_struct('temperature', 0.0, 'max_tokens', 2000)) AS ai
           FROM {NS}.post_attributes p LEFT ANTI JOIN {NS}.corpus_country_reviews done
             ON done.comment_id = p.comment_id AND done.content_hash = p.content_hash
               AND done.model = p.model AND done.prompt_hash = p.prompt_hash AND done.error IS NULL
               AND done.review_version = {literal(COUNTRY_VERSION)}
           WHERE substr(p.month, 1, 4) = {literal(year)} AND p.status = 'success'
             AND p.remote_policy = array('onsite') AND lower(split(p.source_text, '\\n')[0]) RLIKE 'on.?site'
             AND exists(p.evidence.country, quote -> NOT contains(split(p.source_text, '\\n')[0], quote)))""")
        counts = publish()
        log("running", counts)

    assert counts.successful == TOTAL and counts.failed == 0 and counts.pending == 0, "Some posts still need extraction; successful results are saved"
    assert spark.sql(f"SELECT count(*) - count(DISTINCT comment_id) AS n FROM {NS}.post_attributes").first().n == 0
    log("complete", counts)
except Exception as exc:
    counts = publish()
    log("incomplete", counts, str(exc)[:2000])
    raise

# COMMAND ----------
spark.sql(f"""CREATE VIEW IF NOT EXISTS {NS}.post_skills AS
 SELECT DISTINCT comment_id, month, CASE lower(trim(skill))
  WHEN 'postgres' THEN 'postgresql' WHEN 'js' THEN 'javascript' WHEN 'ts' THEN 'typescript'
  WHEN 'reactjs' THEN 'react' WHEN 'react.js' THEN 'react'
  WHEN 'node' THEN 'nodejs' WHEN 'node.js' THEN 'nodejs'
  WHEN 'golang' THEN 'go' WHEN 'k8s' THEN 'kubernetes'
  WHEN 'ruby on rails' THEN 'rails' WHEN 'express.js' THEN 'express'
  WHEN 'vue.js' THEN 'vue' WHEN 'amazon web services' THEN 'aws'
  WHEN 'google cloud platform' THEN 'gcp' ELSE lower(trim(skill)) END AS skill
 FROM {NS}.post_attributes LATERAL VIEW explode(skills) s AS skill
 WHERE status = 'success' AND is_hiring AND length(trim(skill)) > 0""")
spark.sql(f"""CREATE VIEW IF NOT EXISTS {NS}.post_countries AS
 SELECT DISTINCT comment_id, month, country
 FROM {NS}.post_attributes LATERAL VIEW explode(countries) c AS country
 WHERE status = 'success' AND is_hiring""")
spark.sql(f"""CREATE VIEW IF NOT EXISTS {NS}.post_salaries AS
 SELECT p.comment_id, p.month, p.company, p.source_url, compensation.*
 FROM {NS}.post_attributes p LATERAL VIEW explode(p.salary) s AS compensation
 WHERE status = 'success' AND is_hiring""")
spark.sql(f"""CREATE VIEW IF NOT EXISTS {NS}.post_processing_coverage AS
 SELECT month, count(*) AS input_posts, count_if(status = 'success') AS processed_posts,
   count_if(status = 'success' AND is_hiring) AS hiring_ads,
   count_if(status = 'success' AND NOT is_hiring) AS non_hiring_posts,
   count_if(status <> 'success') AS incomplete_posts,
   count_if(status = 'success' AND NOT evidence_quotes_verified) AS evidence_review_posts
 FROM {NS}.post_attributes GROUP BY month""")
dbutils.notebook.exit(json.dumps({"model": MODEL, "input_posts": TOTAL, "successful_posts": counts.successful,
 "failed_posts": counts.failed, "pending_posts": counts.pending, "run_id": RUN_ID}))
