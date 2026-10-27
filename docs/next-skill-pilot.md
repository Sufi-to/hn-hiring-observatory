# Your Next Skill: guided pilot

Run locally with `.venv/bin/python run_local.py --profile tom`, then choose
**Your Next Skill**. This pilot uses the operator's existing Databricks access.
It introduces no public access, accounts, profile storage or additional AI calls.

## What the recommendation means

Choose 1–5 existing normalized skills. A relevant advertisement mentions at least
one of those skills and matches the country, policy and seniority filters.
Recommendations rank other skills by their share of these distinct ads in the
latest three completed calendar months, then alphabetically for ties. A cohort
needs 20 ads; each suggestion needs five supporting ads. Up to three are shown.
The preceding three months provide context, not a ranking factor; comparison
requires complete coverage and 20 prior cohort ads. Zero prior mentions is a
valid zero share. Missing coverage is not zero demand.

The new screen ignores sidebar dates (disabled on that screen). Recommendations
never silently fall back to older periods or lower thresholds. Original HN posts
are examples of technology mentions, not proof of role-level requirements,
remote eligibility, open vacancies or the user's qualifications. Reposts count
as separate advertisements. No learning difficulty or salary outcome is inferred.
Selections survive navigation during the session; profiles are not stored.

## Before each session

1. Verify the visible retrieval time is within seven days and the recent period
   passes coverage checks. Use the existing incremental ingestion/extraction
   workflow in [operations](operations.md) if it does not; the app's Refresh
   results button only clears cached query results.
2. Run `.venv/bin/python quality/verify_next_skill.py --profile tom` to check
   live SQL, counts and evidence against independent Python sets. This uses
   persisted extraction outputs and writes `quality/next-skill-results.json`.
3. Warm the warehouse with an initial request. Record first-request time separately
   from warm requests. The target is five seconds on a warm warehouse; cached UI
   responses should be faster. SQL repeat timings do not measure the app cache.

## Five guided sessions

Ask each developer: “Choose skills you know, find a technology worth investigating,
and show me an advertisement that explains why.” Start timing when the screen is
ready. Avoid explaining the ranking until they have attempted the task.

Record manually, using participant numbers rather than names:

| Participant | Time to suggestion + source | Useful suggestion? | Could explain evidence? | Confusion / next improvement |
| --- | --- | --- | --- | --- |
| 1 | | | | |
| 2 | | | | |
| 3 | | | | |
| 4 | | | | |
| 5 | | | | |

Success: at least four of five identify a useful technology and inspect a
supporting ad within two minutes. Ask what would make them return next month.
Do not treat this small pilot as proof that recommendations improve employment
outcomes. Use the observations to decide the next change before adding accounts,
alerts or public access.

## Failure handling and checks

The UI blocks recommendations if recent months are absent, partial, have failed
or pending ingestion, or have incomplete extraction. Prior gaps suppress trend
values only. Stale retrieval produces a warning. Query failures provide a retry
and reference ID; service details stay out of the UI. Query logs include statement
IDs and durations, or a failure reference and error class.

Offline checks: `.venv/bin/python -m unittest discover -s tests -v`.
The test suite executes SQL against duplicate-heavy fixtures and checks filters,
thresholds, deterministic ties, evidence membership, zero baselines, missing
coverage, navigation, downloads and recoverable failures. Live verification is a
separate read-only check and requires workspace access.
