# HN Job Market Explorer

A Databricks-native analysis of official monthly Hacker News hiring threads,
starting January 2020. Processing runs inside the authenticated Databricks
workspace; there is no external downloader or storage service.

## Project skills

Two reusable Codex skills are maintained in this repository:

- [`hnjob-market-analysis`](skills/hnjob-market-analysis/SKILL.md): query the full
  dataset, define skill growth and salary metrics, and connect charts/chat to the
  correct post-level tables. Example: `Use $hnjob-market-analysis to compare skill
  growth across the last two complete quarters and show the SQL.`
- [`hnjob-extraction-ops`](skills/hnjob-extraction-ops/SKILL.md): compare models,
  check jobs, reuse cached outputs, handle quota failures and finish independent
  QA. Example: `Use $hnjob-extraction-ops to check what validation remains without
  rerunning successful extraction.`

Both are linked into this environment's Codex skills directory. Their automatic
selection remains enabled. Start a new Codex session if they are not yet listed;
the installed links use these repository copies as the maintained source.

## Deployed application

[Open HN Hiring Observatory](https://hn-hiring-observatory-7474647140884875.aws.databricksapps.com)
and sign in with the Databricks workspace account. App name:
`hn-hiring-observatory`. The deployed app's service identity passed a combined
read check over all six required tables/views and a chat count question verified
against reference SQL. It can access 40,065 processed posts and 39,596 hiring ads.
See `quality/deployment-results.json` for the deployment ID and verification.

Deployment is maintained by `databricks.yml`, target `prod`, and `app/app.yaml`.
Resources grant the app `CAN_USE` on the existing warehouse, `CAN_QUERY` on the
chat endpoint, and `SELECT` on the six HN tables/views. App resources inject their
identifiers; the deployed code uses the managed service identity rather than a
personal profile. Only the owner was explicitly granted App management access.

To publish an authorized update:

```sh
databricks bundle validate --strict --target prod --profile tom
databricks apps deploy --target prod --profile tom --auto-approve --skip-validation
databricks apps logs hn-hiring-observatory --profile tom
```

This CLI's `apps validate` supports Node projects only. For this Python app,
`--skip-validation` skips that unsupported validator; strict bundle validation,
Python/UI tests and deployed service-identity checks provide the relevant checks.
`app/runtime_check.py` logs `HNJOB_RUNTIME_CHECK` at managed-app startup; temporary
backend failures are logged without preventing the UI from offering a retry.
Free Edition runtime/quota limits still apply.

## Local application preview

The complete local app is in `app/` and reads the full post-level Databricks
tables. It has six screens: Overview, Skills, Compensation, Explore ads, Ask the
data, and Data coverage. The default date range is the last 12 complete months.
Month, country, work-policy and seniority filters apply to analytics and browsing.
Skills can be compared over time or ranked by share growth; source ads are
paginated and retain original HN links, source text and AI evidence. Charts and
tables offer CSV downloads where useful.

Start it from the repository root with an explicitly selected profile:

```sh
python3 -m venv .venv
.venv/bin/pip install -r app/requirements.txt
.venv/bin/python run_local.py --profile tom
```

Open **http://127.0.0.1:8501**. Use `--port 8502` if needed. The local server binds
only to loopback and uses the selected profile's existing authentication; no tokens
are copied into source files. The UI runs locally; warehouse queries and chat
model calls still run on Databricks and require available compute/quota.

Chat uses a Databricks-hosted model through `ai_query`, with the exact curated
schema and reference metric patterns. A SQL parser rejects writes, unlisted
functions and non-project data sources before executing a generated query, capped
at 200 returned rows. Answers show SQL, results, execution identity and AI caveats.
The existing experimental Genie space is not used or changed. The model remains
fallible; the skill-growth smoke question is checked against reference SQL, not
treated as a comprehensive chat accuracy evaluation.

Compensation charts require explicit currency, period and base/total type, and
exclude invalid bounds. Sparse samples are expected because many ads leave one
of those facts unknown. Other ranges remain visible in the source explorer.

Validation:

```sh
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python quality/verify_app_live.py --profile tom
.venv/bin/python quality/verify_local_ui.py --profile tom
```

The first command uses small fixtures and tests SQL restrictions and UI flows.
The latter commands query Databricks; the first also performs a model call.
Reports are `quality/app-live-results.json` and `quality/local-ui-results.json`.
The same application can also be tested locally without changing the deployment.

## Model comparison and full extraction

Five Databricks-hosted models were compared on the same 20 frozen source posts,
using identical prompts, schemas and generation limits. Raw outputs were scored
before shared cleanup. GPT OSS 120B was selected with 19/20 posts passing every
defined check and 119/120 field checks. See `quality/model-comparison-results.json`.
The sample is a development benchmark, not a corpus-wide accuracy estimate.

The full extraction job **completed successfully**: job `5181643003890`, run
`30070794346507`, notebook `05_extract_all_posts`. It saved successful outputs for
**all 40,065 available nonempty posts**, with **zero failed or pending posts**.
The job also asserted zero duplicate post IDs before publishing all four views.
It checkpoints large yearly groups and retries failed rows;
reruns reuse successful results matching the post hash, model and prompt hash.
There is no recurring schedule.

The output contract for the future application is `workspace.hnjob.post_attributes`:
one row per source post with skills, compensation ranges, seniority, remote policy,
countries, source evidence, model provenance and a processing status. Post-level
attributes do not represent individual vacancies or role-specific eligibility.
The `post_skills`, `post_countries`, `post_salaries` and `post_processing_coverage`
views are published and their catalog schemas have been verified.

Progress and errors are saved in `all_extraction_runs`. Raw model responses are
retained in `all_post_attempts`, with country-context reviews in
`corpus_country_reviews`. Use `sql/inspect_full_extraction.sql` to review them.
The extraction run status is `complete`. Independent warehouse checks now pass:
40,065 distinct successful outputs across 82 months, zero missing input hashes or
incomplete posts, and all four app-facing views queryable. AI classified 39,596
posts as hiring and 469 as non-hiring. Quality checks flag 153 posts for evidence
quote review, 30 for country review, and 4 with invalid salary bounds; these are
follow-up items, not evidence of perfect extraction accuracy. See
`quality/full-extraction-results.json`. Recheck cached outputs without new AI
inference using `python3 quality/verify_full_extraction.py` with profile `tom`.

The skill-growth query also executed successfully: `sql/fastest_growing_skills.sql`
compares Q3 with Q2 2026 by share of hiring advertisements, requiring 20 mentions
in each period. Actual results and the executed SQL are saved in
`quality/skill-growth-results.json`. All six compared months have complete
processing coverage; October is excluded as partial.
The earlier 20-post test remains available separately.

## Verified ingestion result

The historical backfill succeeded: **82 monthly threads, January 2020 through
October 2026, and 43,450 direct-comment records**. All expected comment IDs were
retrieved, with zero duplicate IDs, missing months, pending fetches or fetch errors.
There are 40,065 nonempty candidate advertisements; 3,384 records are
deleted/dead/unavailable and cannot contribute recoverable job text. Candidate
advertisements have now been AI-classified in `post_attributes`; the raw candidate
view deliberately includes non-hiring comments. October 2026 is a partial month.

The successful run is `835977841598627`; machine-readable validation results are
in `quality/ingestion-results.json`.

## Workspace

- Account: `tomastekle20@gmail.com`; CLI profile: `tom`.
- Catalog/schema: `workspace.hnjob` (isolated from existing projects).
- SQL warehouse: existing `Serverless Starter Warehouse`, `616681d29d918fc1`.
- [Manual ingestion job](https://dbc-208a6ca5-ab77.cloud.databricks.com/?o=7474647140884875#job/624810792646052).
- Notebook: `/Users/tomastekle20@gmail.com/hnjob/01_ingest_hn`.
- Non-secret deployment identifiers: `deployment/workspace.json`.

## Ingestion

The notebook first checks direct access to the official HN API. If access fails,
it stops without creating data tables. There is no local-download fallback.

The `whoishiring` account's submissions discover the canonical monthly stories.
Only `Ask HN: Who is hiring? (Month Year)` stories from that account are selected.
Each direct child is downloaded; nested discussions are excluded from candidate
advertisements. The raw layer is deliberately not labeled as confirmed jobs;
AI classification is a later processing stage.

Tables and views:

| Object | Meaning |
| --- | --- |
| `raw_threads` | Thread manifest, timestamps, direct child IDs, raw API JSON |
| `raw_comments` | One row per direct comment; original HTML, cleaned text, hash, status, source URL |
| `ingestion_runs` | Run IDs, timestamps, counts and errors |
| `candidate_ads` | Available direct comments, excluding deleted/dead/empty records |
| `ingestion_coverage` | Every month since 2020, expected/retrieved/failed/pending counts |

Deleted and dead comments retain a status record. Missing historical text cannot
be recovered from the current API. Any month missing from discovery is visible
in coverage; it is never silently presented as zero hiring activity.

There is **no schedule**. Trigger the job manually using the Jobs UI or CLI:

```sh
# Full historical backfill, resuming comments not successfully retrieved before.
databricks jobs run-now --profile tom --no-wait --json \
  '{"job_id":624810792646052,"notebook_params":{"mode":"backfill","max_threads":"0"}}'

# Refresh the latest three discovered monthly threads and discover new ones.
databricks jobs run-now --profile tom --no-wait --json \
  '{"job_id":624810792646052,"notebook_params":{"mode":"incremental","max_threads":"0"}}'

# Revisit all months, including historical edits/deletions.
databricks jobs run-now --profile tom --no-wait --json \
  '{"job_id":624810792646052,"notebook_params":{"mode":"reconcile","max_threads":"0"}}'
```

The `max_threads` parameter optionally limits a run to a pilot. Backfill selects
the earliest months still needing retrieval. Checkpoints are committed in batches
of at most 500 comments. Re-running the job does not duplicate comment IDs.
Transient errors do not overwrite an existing successful retrieval. Failed or
unavailable items can be retried in a later backfill.

The notebook limits network concurrency to eight requests and retries transient
failures three times. Free Edition quota exhaustion can require waiting for a
reset and rerunning the same job. Do not launch competing runs.

## Validation

```sh
python3 -m unittest discover -s tests -v
python3 -m py_compile notebooks/01_ingest_hn.py
```

Run `sql/verify_ingestion.sql` in the SQL warehouse to inspect coverage, duplicate
IDs, valid candidate relationships, and job history. A successful job alone does
not guarantee full coverage: inspect pending and failed item counts as well.

## Remaining application stages

The earlier extraction notebook (`notebooks/02_extract_roles.py`) and Genie
configuration (`deployment/genie-space.json`) remain experimental. The local
Streamlit application (`app/`) now uses the complete post-level data directly.
The dedicated post-attribute test job is `453515354614183`, using
`notebooks/03_test_first20_ai_functions.py`. It is fixed to the first 20 available
posts ordered by posting time and comment ID. `ai_query` extracts skills, salary,
seniority, remote policy, and countries using a strict JSON schema and a
Databricks-hosted foundation model. `test_first20_inputs` freezes the cohort;
reruns do not advance to posts 21+ and successful results are cached by version.
The experimental role-level extraction job remains `1108574991787472`;
its separate results table is `role_test_first20_results`.
The earlier five-comment review is recorded in
`quality/extraction-review.md`. This is not a completed accuracy evaluation.

[HN Hiring Observatory Genie space](https://dbc-208a6ca5-ab77.cloud.databricks.com/genie/rooms/01f1cffc7e071e938b8c07859b83267a)
uses six curated views, five example SQL questions and 20 benchmark questions.
The benchmark definitions are prepared; actual benchmark acceptance is pending.

The small extraction model did not pass the reviewed examples. The completed
five-model comparison selected GPT OSS 120B for the successful full-corpus run.
The separate country-aware 20-post test uses
`databricks-gpt-oss-120b`, extraction version `post-fields-v1`, and job run
`46984684545515`. Results are stored in `workspace.hnjob.test_first20_results`;
source-reviewed expectations and checks are stored in `test_first20_expectations`
and `test_first20_validation`. The checks cover country/remote policy, explicit
seniority, representative named skills, salary ranges and verbatim evidence.
They are a small functional test, not a corpus-wide accuracy estimate.
The completed post-level test returned 20/20 successful outputs and passed all
defined source checks after a focused country-context correction. It preserves
the original AI JSON and the separate header-country review for audit. Literal
management titles are normalized to leadership, and unconfirmed compensation
types remain unspecified. See `quality/first20-results.json` and
`sql/inspect_first20.sql` for results and review queries. These are development
checks refined on this sample, not held-out accuracy measurements.
One live Genie coverage query passed; the later counting/unsupported-question
checks need repeating after the extraction view migration finishes.

Routine ingestion and extraction reuse published views to avoid interrupting
readers. When deliberately upgrading the extraction schema or version, run once
with notebook parameter `publish_views=true` while readers are idle; leave it
false for ordinary batches.

The older app prototype remains staged at `/Users/tomastekle20@gmail.com/hnjob/app`.
The production app uses the bundle-managed source path recorded in
`deployment/workspace.json`. Existing unrelated Apps were not replaced or deleted.

The earlier role-level views, Genie configuration, and workspace-staged prototype
still refer to the small role-based dataset. The current local app uses
`post_attributes` and the `post_*` views; it does not use those earlier objects.

1. Review the flagged evidence/country outputs and exclude invalid salary bounds
   before relying on compensation charts; independent coverage QA has passed.
2. Continue user-testing the deployed app's filters, source browsing, exports and chat.
   Counts represent distinct advertisements; a post's skills, seniorities and
   countries are not automatically attributable to every advertised role.
3. Broaden chat evaluation beyond the development smoke question. If choosing
   Genie later, migrate its configuration deliberately and validate reference SQL.
4. Maintain the authorized deployment through the `prod` bundle target and inspect
   the deployed runtime checks after updates.

The account had an available App slot for this deployment. Check current capacity
before creating additional Apps. Free Edition Apps can stop automatically after
24 hours and may need restarting.

Run all local UI and parser tests with the project virtual environment:

```sh
.venv/bin/python -m unittest discover -s tests -v
```

The UI tests use representative warehouse/Genie responses; they do not establish
live deployed permissions, extraction accuracy, or production performance.
