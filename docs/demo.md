# Demo and presentation guide

## Media in this repository

The README's 25-second GIF and 75-second captioned MP4 are **illustrated
walkthroughs using verified saved outputs**. They explain the implemented workflow;
their layouts are explanatory illustrations, not captures of the Streamlit UI.
They require no Databricks login to play when the viewer has repository access.
The MP4 has embedded captions and no audio.

| Scene | What it demonstrates | Evidence |
| --- | --- | --- |
| Overview | 40,065 processed posts, 39,596 hiring ads, 82 months | `quality/full-extraction-results.json` |
| Skill growth | Q3 vs Q2 2026; Rails +1.91 percentage points | `quality/skill-growth-results.json` |
| Ask and inspect | A supported natural-language question, generated SQL and verified counts | `quality/app-live-results.json` |
| Trace the source | Remote/Rust post matches with original HN links | `quality/app-chat-results.json` |
| Architecture | Ingestion, structured extraction, curated tables, analytics and restricted SQL | Application and pipeline source |

Values describe the saved October 25, 2026 snapshot. The visual code reads these
reports directly. It does not invent market observations or invoke models.

Rebuild with Pillow (installed with the app's Streamlit dependency) and FFmpeg:

```sh
.venv/bin/python docs/build_demo.py
```

The build produces a GIF, MP4, static poster and five scene images in
`docs/assets/`. It does not access accounts or change the deployed application.

## Recording the actual UI

Use the local app with the real dataset or sign in to the deployed app. Record
only the app viewport; keep account menus, terminal windows and credentials out
of frame. Use a 1440×900 or larger viewport and a readable zoom level.

For a 25-second GIF, capture this sequence:

1. **0–5 s — Overview:** show the month filters, headline metrics and hiring trend.
2. **5–10 s — Skills:** show the three-month Q3/Q2 2026 comparison, threshold 20,
   and the Rails growth row with its counts and denominators.
3. **10–17 s — Ask the data:** ask “Which skills grew fastest in Q3 2026 versus
   Q2 2026?” Reveal the returned SQL and result table. Trim the wait, not the result.
4. **17–25 s — Explore ads:** select remote and Rust, expand a result, and show the
   original HN link and source text. Keep the post-level eligibility caveat visible.

For a 60–90 second narrated recording, use this suggested script and adjust it to
your own voice:

> Hacker News hiring threads contain useful information, but it is spread across
> thousands of free-text posts. This project turns that history into a searchable
> analytics application on Databricks.
>
> The pipeline processed 40,065 available posts across 82 monthly threads. It
> extracts skills, compensation, seniority, work policies and countries while
> keeping source text and evidence for review.
>
> Here, I compare skill mentions as a share of hiring ads. Rails rose from 2.57
> percent to 4.48 percent between Q2 and Q3 2026. The denominators matter because
> the total number of hiring ads fell during that period.
>
> I can also ask a question in plain English. The app shows the generated SQL and
> returned data, and checks queries before execution. For individual examples,
> I can inspect the original advertisement and follow its Hacker News link.
>
> The engineering work includes resumable inference, a five-model development
> comparison, preserved unknown values, automated checks, and deployment using a
> managed service identity. The data measures posting activity, not actual hires.

Replace the illustrated media only after reviewing the recording for readable
text, correct results, account details and an accurate label.

## Sharing with recruiters

The repository is private and the deployed app requires approved workspace access.
Send the walkthrough as a file, grant repository access to a specific reviewer,
or review and authorize a public portfolio/repository separately. A link to the
private README alone does not grant access. No repository visibility or workspace
access permissions are changed by this documentation update.
