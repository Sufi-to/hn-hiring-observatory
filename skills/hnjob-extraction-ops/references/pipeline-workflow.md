# Pipeline workflow and recovery

## Choose the existing artifact

Identifiers below describe the recorded project. Prefer the current
`deployment/workspace.json` if they change. Workspace host:
`https://dbc-208a6ca5-ab77.cloud.databricks.com`, namespace `workspace.hnjob`,
explicit CLI profile `tom`, SQL warehouse `616681d29d918fc1`.

| Work | Source and control |
| --- | --- |
| Fetch official HN threads/comments | `notebooks/01_ingest_hn.py`, job 624810792646052 |
| Five-field first-20 development test | `notebooks/03_test_first20_ai_functions.py`, job 453515354614183 |
| Model comparison | `pipeline/compare_models_body.py` generates notebook 04, job 1011439504028854 |
| Full post extraction | `pipeline/extract_all_body.py` generates notebook 05, job 5181643003890 |
| Build generated notebooks | `python3 pipeline/build_pipeline.py` |
| Verify persisted results | `python3 quality/verify_full_extraction.py` |

Notebook 03's prefix before its first `# COMMAND ----------` defines the shared
prompt, strict JSON schema, model default and country-review configuration.
`pipeline/build_pipeline.py` incorporates it into notebooks 04 and 05, and copies
validation SQL from `quality/build_first20_validation.py` for comparison scoring.
Rebuilding writes generated notebooks and validation request artifacts; inspect
those changes before upload. Use existing `deployment/*-job.json` definitions
for authorized updates. No recurring schedules are configured.

Notebook 02/job 1108574991787472 is the earlier experimental role extractor.
Do not confuse it with the full post-level extractor.

## Establish state before doing work

The recorded full run is 30070794346507; its task run is 746162627006741.
It terminated successfully with 40,065 successful outputs, zero failed/pending,
and an in-job assertion of zero duplicate comment IDs. Independent SQL QA was
initially blocked by compute availability and subsequently completed. Check the
current reports for verified counts and remaining quality flags instead of
assuming either the old blocker or successful coverage establishes factual accuracy.

```sh
databricks jobs get-run 30070794346507 --profile tom -o json
databricks jobs get-run-output 746162627006741 --profile tom -o json
```

`get-run-output` takes the task run ID. Inspect its `error` and
`notebook_output.result`, not just the parent's state. If a run is still active,
monitor it rather than submitting a duplicate. Prefer checkpoint changes and
specific errors in progress updates over repeatedly printing unchanged counts.

`pipeline/monitor_full_run.py` is pinned to the recorded run. Update its run ID
when deliberately monitoring a new run; do not mistake an old successful run for
progress on the new one.

## Ingestion invariants

Use canonical monthly threads from the official `whoishiring` account since
January 2020. Store direct comments, raw HTML/API payloads, cleaned text, source
links, content hashes and unavailable statuses. Nested replies are not candidate
advertisements. `candidate_ads` is available nonempty text, not confirmed jobs.

Ingestion modes are `backfill`, `incremental` (latest three discovered months),
and `reconcile` (revisit all months). Read the notebook and README before choosing
one. Incremental mode is not a complete historical edit/deletion reconciliation.
Use existing idempotent/checkpoint behavior; do not replace the raw tables to
refresh a few months. Track missing months and fetch errors explicitly.

## Fair model comparison

The frozen cohort is `test_first20_inputs`, ordered chronologically; expectations
are in `quality/first20_expected.json`. Results are recorded in
`quality/model-comparison-results.json`, backed by benchmark attempt/run/check/
score tables. The recorded winner was `databricks-gpt-oss-120b` with 19/20 raw
complete-post checks and 119/120 field checks. The normalized single-model test's
20/20 result is a different result; do not mix the scores.

Use the same prompt, strict output schema, temperature 0 and initial token limit
for every candidate in one comparison. Count missing and invalid model responses
as failures. The existing selection order is complete posts, field checks, valid
outputs, then lower observed batch duration. Batch timings include query overhead
and cannot be extrapolated linearly to the corpus. Add newer, varied review cases
when estimating generalization; keep the frozen development cohort identifiable.

The code uses `ai_query` to compare explicit model endpoints with a nested output
schema. Consult the available AI Functions skill for current alternatives; do
not silently change extraction semantics or assume endpoint names remain valid.
Report unavailable models explicitly rather than presenting them as evaluated.

## Full extraction and cache handling

- `extraction_corpus`: snapshot of current candidate inputs.
- `all_post_attempts`: append-only raw model outputs/errors and version provenance.
- `selected_extraction_model`: comparison winner and prompt/version identity.
- `corpus_country_reviews`: separate focused onsite-header country responses.
- `all_extraction_runs`: totals, status, timestamps and errors.
- `post_attributes`: current one-row-per-post outputs with quality flags.
- `post_skills`, `post_countries`, `post_salaries`, `post_processing_coverage`:
  app-facing views created after processing.

The selected model's matching benchmark successes seed the full cache. Full
extraction groups inputs by year, persists each group, and retries unresolved
rows up to three attempts (initial 7,000 output tokens, retries 12,000). Valid
successes outrank subsequent errors. A rerun with the same hashes reuses them;
changing the prompt/schema/model can cause new inference across the corpus.
Do not change versions as a way to retry transient failures.

Shared cleanup handles explicit management titles, leaves compensation type
unspecified unless base is stated, and reviews selected onsite header countries.
Original outputs remain stored. Failed/unresolved country reviews can leave
`needs_review` even when core extraction status is `success`.

Views use `CREATE VIEW IF NOT EXISTS` to keep ordinary refreshes from disrupting
readers. Definition changes therefore need an intentional migration; rerunning
does not replace an existing view definition. Refresh after input edits/deletions
must rebuild the corpus/current outputs and reconcile exclusions, not only append.

## Verification and handoff

For the unchanged historical corpus, `quality/verify_full_extraction.py` checks
40,065 distinct successful outputs, 82 months (2020-01 to 2026-10), one model/prompt,
zero missing input hashes/incomplete posts, four queryable views, and complete
run status. Its historical totals/dates are intentionally fixed: update expected
values from verified ingestion when new source data arrives. Do not weaken an
assertion just to make an unexpected discrepancy pass.

The script also records hiring/non-hiring counts and evidence/country/salary
quality flag totals. It overwrites the results report only after successful checks.
`sql/verify_full_extraction.sql` and `sql/inspect_full_extraction.sql` support manual
inspection without repeating inference. Inspect flags before relying on salary
charts; processing success is not evidence that all claims are correct.

If compute is unavailable, report separately: job result, in-job assertions,
catalog object/schema checks, and unexecuted SQL/semantic checks. Save the blocker
and resume command in the handoff. Updating documentation or reading catalog
metadata does not require rerunning the extraction or starting a new model job.
