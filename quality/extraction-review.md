# Initial extraction review

The first live smoke test used Databricks-hosted `databricks-gpt-oss-20b`
with `roles-v1`. Five actual comments produced 15 role records. This is a
development smoke test, not a completed accuracy benchmark.

| HN comment | Review |
| --- | --- |
| 24342567 | Bolt: correctly retained unknown salary, seniority, remote policy, and skills. |
| 26249813 | Animato: correctly extracted EUR 2300–3800 monthly, Angular/Ionic/TypeScript and UTC scope. Incorrectly labeled unspecified contract compensation as base. |
| 26305233 | Applied Intuition: split nine bullet roles and inherited onsite policy, but incorrectly placed VISA in remote restrictions and omitted a recruiter role listed in the header. |
| 27746500 | blindnet: recognized Java/Scala roles and EUR upper salary bound without inventing an annual period. Remote restrictions incorrectly held the generic word Remote instead of France; generic security job family was emitted as a technology skill. |
| 28042506 | ICS: correctly extracted seniority, AWS, remote policy, and preferred regions without inventing salary. |

`roles-v2` tightens these instructions, adds separate evidence excerpts for
skills, seniority, remote policy and compensation, and normalizes invalid
remote-restriction placeholders out of curated views. Versioned results prevent
silently mixing the initial output with revised extraction.

The next gate is review of the revised outputs, followed by the planned
100-comment labeled evaluation. Full-corpus extraction must not be represented
as quality validated until that evaluation meets the acceptance targets.

The v2 rerun succeeded technically (five comments, 19 role records), but did
not pass semantic review: it inferred onsite policy for Bolt without an explicit
policy, continued to label unspecified compensation as base, and split a single
hybrid-app/full-stack opening into duplicate role groups. France restrictions
and generic-security skill handling improved. The small model is not approved
for full-corpus extraction. `roles-v3` evaluates the larger Databricks-hosted
`databricks-gpt-oss-120b` on the same five cases before expanding the pilot.
