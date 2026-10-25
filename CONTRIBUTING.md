# Development guide

This repository contains the application, Databricks ingestion and extraction
code, metric SQL, and saved validation reports. Start with the [source map in the
README](README.md#explore-the-source) to find the relevant component.

## Set up and run tests

Use Python 3.11 or newer and run commands from the repository root:

```sh
python3 -m venv .venv
.venv/bin/pip install -r app/requirements.txt
.venv/bin/python -m unittest discover -s tests -v
```

The existing tests cover ingestion parsing, query parameter binding, SQL
restrictions, Streamlit screens, chat rendering and cache serialization. They use
small fixtures and require no Databricks account, credentials or model calls.
GitHub Actions runs this suite on pushes and pull requests using Python 3.11.

## Work with the live application

The UI runs locally, while data queries and chat inference run in Databricks.
Use an explicitly selected authenticated profile. For the original project
workspace, the selected profile is `tom`:

```sh
.venv/bin/python run_local.py --profile tom
```

Open http://127.0.0.1:8501. The checked-in settings in
[`deployment/workspace.json`](deployment/workspace.json) describe the original
workspace. A different workspace needs its own tables, SQL warehouse, model
access and configuration; cloning the repository does not provision them.

See the [operations guide](docs/operations.md) for live verification, ingestion,
extraction and deployment. Live checks consume available warehouse/model quota.
Saved JSON reports describe the recorded run, rather than a check of the current
workspace state. Keep reports and their date/provenance together when refreshing
evidence. Do not rerun successful extraction merely to validate a UI change.

## Make changes reviewable

- Keep analytics at the advertisement grain and show denominators for shares.
- Preserve unknown compensation fields and separate currency, period and type.
- Retain original HN links, extraction evidence and visible quality flags.
- Use bound parameters for user input and keep chat queries within the existing
  read-only SQL restrictions.
- Run the tests relevant to code changes. For UI changes, also review the affected
  screen with representative data and its loading, empty and error states.
- Keep credentials, local environments, caches and generated runtime logs out of
  commits. Commit only the source and evidence needed to review the change.

## Refresh the demo

The [demo guide](docs/demo.md) documents the real captures, captioned GIF/MP4,
build prerequisites and source hashes. Rebuild media with:

```sh
.venv/bin/python docs/build_demo.py
```

Review all six scenes for readable captions, correct periods, source context and
accidental account details. Keep the screenshot-tour label accurate; a sequence
of still captures should not be described as a continuous screen recording.
