# Data contract and query pitfalls

## Source and grain

Official monthly `Ask HN: Who is hiring?` stories are discovered from the
`whoishiring` account through the HN Firebase API. Only direct child comments are
candidate ads; nested discussion is excluded. Deleted/dead/unavailable comments
retain raw status records and cannot supply recoverable text.

The recorded October 25, 2026 backfill contains 82 threads, January 2020 through
October 2026, and 40,065 nonempty available candidate posts. October is partial.
These are a historical snapshot, not constants for future refreshes. Consult
`quality/ingestion-results.json` and the live coverage views.

## Complete output contract

`workspace.hnjob.post_attributes` has one row per source comment:

| Fields | Meaning |
| --- | --- |
| `comment_id`, `thread_id`, `month`, `posted_at` | Source keys and time; month is `YYYY-MM` |
| `source_url`, `source_text`, `content_hash`, `fetched_at` | Source and input provenance |
| `model`, `prompt_hash`, `extraction_version`, `extracted_at` | Extraction provenance |
| `company`, `is_hiring`, `status`, `error` | Company, AI classification, processing outcome |
| `skills` | Array of explicitly named technologies across the post |
| `seniority` | Array: intern, junior, mid, senior, staff, principal, leadership, unspecified |
| `remote_policy` | Array: remote, onsite, hybrid, unspecified |
| `countries`, `country_scope` | Full country names and scopes: listed_countries, worldwide, region_only, unspecified |
| `salary` | Array of compensation structs, described below |
| `evidence` | Struct containing country, remote and salary quote arrays |
| `country_review_status` | reviewed, needs_review, not_needed |
| `salary_bounds_valid`, `evidence_quotes_verified` | Mechanical quality flags, not semantic accuracy guarantees |
| `raw_output`, `country_review_output` | Original extraction and focused review JSON |

Analytics usually filter `status = 'success' AND is_hiring = true`. Preserve
non-hiring and unavailable records for coverage, rather than calling them jobs.

Each salary struct has `title`, `minimum`, `maximum`, `currency`, `period`, `type`,
and `original_text`. A missing range is an empty array, not a zero salary.
Bounds can be null; do not invent the other bound. An unspecified compensation
type or period is not evidence for base or annual salary. No FX conversion or
annualization was performed. The title can be null and is not a reliable role key.

An empty countries array can mean worldwide, region-only, or unknown; check
`country_scope`. A listed country can be a work location without proving remote
eligibility. Explicitly unresolved seniority/policy is `unspecified`.

## App-facing views

| Object | Grain and behavior |
| --- | --- |
| `post_skills` | Distinct comment/month/normalized skill; successful hiring posts only |
| `post_countries` | Distinct comment/month/country; successful hiring posts only |
| `post_salaries` | One row per compensation entry; includes source URL and company |
| `post_processing_coverage` | Per-month input, processed, hiring, non-hiring, incomplete and evidence-review counts |

`post_skills` normalizes selected aliases such as postgres/postgresql, js/javascript,
golang/go, and k8s/kubernetes. It is not an exhaustive technology taxonomy.
Do not silently merge semantically different technologies.

`post_salaries` does not filter invalid bounds or carry every quality flag. Join
`post_attributes` by `comment_id` when filtering `salary_bounds_valid` or examining
evidence. Never join exploded skills, countries and salaries and then count raw
rows: that multiplies advertisements. Aggregate each side or use distinct IDs.

The earlier `roles`, `advertisements`, and role-level extraction artifacts are
experimental, small-cohort outputs. The staged `app/` and
`deployment/genie-space.json` still need migration; do not assume they use the
full dataset simply because they already exist.

## Query and validation resources

- `sql/fastest_growing_skills.sql`: growth example with explicit periods and sample
  thresholds. Check the current saved execution report before describing it as tested.
- `sql/verify_full_extraction.sql`: coverage, uniqueness, input hash reconciliation,
  quality flag totals and monthly checks.
- `quality/verify_full_extraction.py`: runs those read-only checks plus view counts
  and provenance, then saves `quality/full-extraction-results.json` on success.
- `quality/full-extraction-results.json`: distinguishes successful job assertions
  from independent warehouse QA. Read its current contents instead of assuming
  every check passed.
- `quality/skill-growth-results.json`: execution status of the growth query. Only
  a successful result with actual rows supports a ranking.

Hacker News ads are a self-selected source, and technical mentions can describe a
product subsystem or a nice-to-have. Describe measures as mentions in HN hiring
ads rather than universal job requirements. Mechanical schema/evidence checks and
20-post development comparisons do not establish corpus-wide factual accuracy.
