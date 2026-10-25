# Demo and presentation guide

## Media in this repository

The README's **32-second GIF and captioned MP4 use actual browser captures of the
running Streamlit app connected to Databricks**. The tour has six chapters, short
dissolves, reading pauses and an animated progress indicator. Captions explain
the workflow in larger text, and the final architecture card is an illustration.
This is an edited screenshot tour, not a continuous screen recording. No cursor
actions, typing animation or loading times are simulated. Both files require no
Databricks login to play when the viewer has repository access; the MP4 has no audio.

| Scene | What it demonstrates | Evidence |
| --- | --- | --- |
| Overview | Actual hiring activity chart; full corpus: 40,065 processed posts and 82 months | [Capture](assets/captures/01-overview.jpg) · [Coverage report](../quality/full-extraction-results.json) |
| Track skills | Python, TypeScript and Rust share over time | [Capture](assets/captures/02-skills.jpg) |
| Skill growth | Q3 vs Q2 2026; Rails +1.91 percentage points | [Capture](assets/captures/03-growth.jpg) · [Recorded results](../quality/skill-growth-results.json) |
| Ask and inspect | Actual generated SQL, returned counts and growth chart | [Capture](assets/captures/05-sql-wide.jpg); counts agree with the recorded growth report |
| Trace the source | Expanded Close advertisement, AI attributes, original text and HN link | [Capture](assets/captures/06-source.jpg) · [Original HN post](https://news.ycombinator.com/item?id=49615973) |
| Architecture | Ingestion, structured extraction, curated tables, analytics and restricted SQL | [Application](../app/) · [Extraction notebook](../notebooks/05_extract_all_posts.py) |

Captured October 25, 2026 with the previously selected `tom` profile. The overview
and trend views use October 2025–September 2026. Growth compares Q2/Q3 2026 with
at least 20 mentions each quarter and all hiring ads as denominators (934 and 714).
The source example is an original September 2026 post, found with text search
`Close`; it is not presented as a role-specific eligibility match.

The raw captures are in `docs/assets/captures/`. The renderer only crops and scales
those images; it does not redraw results or alter UI data. Its build makes no
account or model calls. [provenance.json](assets/provenance.json) records hashes of
captures and reports. The GIF is 1280×840, loops every 32 seconds, and is about
2.6 MB; the H.264 MP4 provides the same tour with a smaller download.

Rebuild with Pillow (installed with the app's Streamlit dependency), FFmpeg with
H.264 support, and the DejaVu Sans fonts. The renderer expects fonts in
`/usr/share/fonts/truetype/dejavu/` on Linux:

```sh
.venv/bin/python docs/build_demo.py
```

The build produces a GIF, MP4, static poster and six scene images in
`docs/assets/`. It does not access accounts or change the deployed application.

## Focused Ask and Inspect demo

The separate [25-second chat GIF](assets/ask-inspect.gif) shows one complete live
interaction: empty chat → partial question → full question → submitted question
and processing state → returned answer → expanded SQL → result table → chart.
The question is **“Which skills grew fastest in Q3 2026 versus Q2 2026?”**

Input states and the processing screen were captured from the running app, along
with the actual result. It is an edited sequence of screenshots: pauses and
waiting time are shortened and do not represent inference latency. Cropping
removes the sidebar while keeping the chat input and conversation visible.
No cursor actions or results are drawn onto the interface.

The result contains Rails, AI, Node.js, React Native and LLMs, with total-ad
denominators 934 and 714. The builder parses the captured accessibility table and
checks all five rows' counts, denominators, shares and growth against the
[saved reference results](../quality/skill-growth-results.json) before rendering.
It uses no additional model or warehouse calls.

- [Raw chat captures and visible SQL/result evidence](assets/chat-captures/)
- [Static question-entry preview](assets/ask-inspect-preview.png)
- [Chat media provenance and capture hashes](assets/ask-inspect-provenance.json)
- [Reproducible renderer](build_chat_demo.py)

Rebuild independently of the main tour with the same Pillow/font prerequisites:

```sh
.venv/bin/python docs/build_chat_demo.py
```

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

Replace the screenshot tour only after reviewing the recording for readable
text, correct results, account details and an accurate label.

## Sharing with recruiters

The repository is private and the deployed app requires approved workspace access.
Send the walkthrough as a file, grant repository access to a specific reviewer,
or review and authorize a public portfolio/repository separately. A link to the
private README alone does not grant access. No repository visibility or workspace
access permissions are changed by this documentation update.
