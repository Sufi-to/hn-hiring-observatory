"""Generate warehouse SQL checks from source-reviewed first-20 expectations.

This file does not call an LLM or process the corpus locally. The actual
comparisons execute in Databricks SQL and persist a review table.
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
rows = json.loads((ROOT / "first20_expected.json").read_text())
assert len(rows) == 20 and len({row["comment_id"] for row in rows}) == 20


def lit(value):
    return "'" + value.replace("\\", "\\\\").replace("'", "''") + "'"


schema = "STRUCT<comment_id:BIGINT,countries:ARRAY<STRING>,country_scope_required:ARRAY<STRING>,remote_policy:ARRAY<STRING>,seniority_required:ARRAY<STRING>,seniority_forbidden:ARRAY<STRING>,skills_required:ARRAY<STRING>,salary_min:DOUBLE,salary_max:DOUBLE,currency:STRING>"
values = ",\n".join("(" + lit(json.dumps(row)) + ")" for row in rows)
expected_sql = f"""CREATE OR REPLACE TABLE workspace.hnjob.test_first20_expectations USING DELTA AS
SELECT e.* FROM (SELECT from_json(value, {lit(schema)}) AS e FROM VALUES {values} AS t(value))"""

validation_sql = """CREATE OR REPLACE TABLE workspace.hnjob.test_first20_validation USING DELTA AS
WITH normalized AS (
 SELECT r.*, array_distinct(transform(skills, s -> CASE lower(trim(s))
  WHEN 'ruby on rails' THEN 'rails' WHEN 'ruby/rails' THEN 'rails'
  WHEN 'reactjs' THEN 'react' WHEN 'react.js' THEN 'react'
  WHEN 'node' THEN 'nodejs' WHEN 'node.js' THEN 'nodejs'
  WHEN 'express.js' THEN 'express' WHEN 'expressjs' THEN 'express'
  WHEN 'vue.js' THEN 'vue' WHEN 'vuejs' THEN 'vue'
  WHEN 'golang' THEN 'go' WHEN 'postgres' THEN 'postgresql'
  WHEN 'js' THEN 'javascript' WHEN 'ts' THEN 'typescript'
  WHEN 'amazon web services' THEN 'aws' WHEN 'google cloud platform' THEN 'gcp'
  WHEN 'k8s' THEN 'kubernetes' ELSE lower(trim(s)) END)) AS normalized_skills
 FROM workspace.hnjob.test_first20_results r
), checks AS (
 SELECT r.test_rank, r.comment_id, r.company, r.source_url,
   r.status = 'success' AND r.is_hiring AS extraction_ok,
   array_sort(r.countries) = array_sort(e.countries) AS country_ok,
   size(array_except(coalesce(e.country_scope_required, array()), r.country_scope)) = 0 AS country_scope_ok,
   array_sort(r.remote_policy) = array_sort(e.remote_policy) AS remote_ok,
   size(array_except(coalesce(e.seniority_required, array()), r.seniority)) = 0
     AND size(array_intersect(coalesce(e.seniority_forbidden, array()), r.seniority)) = 0 AS seniority_ok,
   array_except(e.skills_required, r.normalized_skills) AS missing_required_skills,
   CASE WHEN e.salary_min IS NULL THEN
     NOT exists(r.salary, s -> s.minimum IS NOT NULL OR s.maximum IS NOT NULL)
     ELSE exists(r.salary, s -> s.minimum = e.salary_min AND s.maximum = e.salary_max
       AND s.currency <=> e.currency AND (s.period IS NULL OR s.period = 'unspecified')) END AS salary_ok,
   forall(concat(r.evidence.country, r.evidence.remote, r.evidence.salary),
     quote -> length(quote) > 0 AND contains(r.source_text, quote))
     AND (size(r.countries) = 0 OR size(r.evidence.country) > 0) AS evidence_quotes_ok
 FROM normalized r JOIN workspace.hnjob.test_first20_expectations e USING (comment_id)
) SELECT *, extraction_ok AND country_ok AND country_scope_ok AND remote_ok AND seniority_ok
  AND size(missing_required_skills) = 0 AND salary_ok AND evidence_quotes_ok AS all_checks_passed
FROM checks"""
for name, statement in [("expected", expected_sql), ("validate", validation_sql)]:
    (ROOT / ("first20-" + name + "-request.json")).write_text(json.dumps({
        "warehouse_id": "616681d29d918fc1", "statement": statement, "wait_timeout": "10s"
    }, indent=2) + "\n")
