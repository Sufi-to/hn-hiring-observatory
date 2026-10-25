---
name: hnjob-market-analysis
description: Analyze this project's Hacker News hiring data in Databricks, write skill-growth and salary SQL, or define metrics for its charts and Genie chat. Use for the HN Job Market Explorer's post-level dataset, not general employment-market research.
---

# HN Job Market Analysis

Use the maintained checkout's `deployment/workspace.json`, `README.md`, and relevant
`quality/*results.json` for workspace identifiers and observed state. The current
checkout is `/home/sufi-to/projectdb/hnjob`; prefer an active copy of that project
when working elsewhere. Resolve project paths below against that checkout, not
the installed skill directory. Do not assume historical snapshots are current.

## Data and execution

- Read [references/data-contract.md](references/data-contract.md) before composing
  queries or connecting an app. The full dataset is `workspace.hnjob.post_attributes`
  and its `post_*` views. Older role-based objects contain experimental samples.
- For live Databricks work, use the available `databricks-core` and
  `databricks-data-discovery` skills. Route natural-language data questions to
  Genie first; use their documented fallback if unavailable. Reuse the user's
  chosen `tom` profile for this project and pass it explicitly. A different
  account/workspace requires the user's selection.
- Query persisted extraction results. Analytics must not call AI Functions again
  for each chart or chat question. Run the SQL when compute is available, and
  provide the actual SQL and returned results when requested.
- If execution is rejected, report the exact blocker and distinguish prepared
  SQL from successful execution. Do not manufacture rankings from model knowledge
  or treat an error report as query results.

## Metric decisions

- Count distinct `comment_id` among successful, AI-classified hiring posts. This
  measures advertisements, not vacancies, people hired, or the entire tech market.
- A post may contain several roles. Its combined skills, countries, seniorities,
  and work policies do not prove that every role has each attribute. Do not infer
  role-level combinations or exact remote eligibility from post-level arrays.
- For growth, state the periods, denominator, ranking metric, and minimum sample
  size. An appropriate default is two adjacent complete three-month periods,
  ranking by percentage-point increase in share of hiring ads. Distinguish this
  from raw count growth and relative percentage growth. Honor a user-specified
  alternative and label it clearly.
- Exclude partial months and verify coverage before interpreting missing rows as
  zero demand. The saved example `sql/fastest_growing_skills.sql` compares Q3 with
  Q2 2026 and requires 20 mentions in each. Update dates for newer data; this
  threshold intentionally excludes emerging skills with a small or zero baseline.
- Keep unknown salary facts unknown. Compare compatible currency, period, and
  compensation type; do not infer USD from a bare dollar sign, infer annual pay
  from magnitude, or combine base with total compensation. Inspect source evidence
  and validity flags for salary analysis.

## App and chat handoff

Before presenting a complete time series, inspect extraction coverage and pending
quality checks. Expose the period, sample count, source links, and meaningful
unknowns alongside metrics. For chat, show generated SQL and its source tables;
distinguish an unsupported question from a true zero result.

Use the Databricks Apps and app-design skills for actual app implementation.
Existing staged app and Genie configuration require migration to the complete
post-level contract. Creating this skill does not authorize deploying an app or
replacing an existing one.
