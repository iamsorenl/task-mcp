# Results: greenhouse

Agent model `gpt-oss:20b`, run 2026-10-30. Token counts are Ollama's own (`prompt_eval_count`, summed over every turn of a task). Tool chars are characters of tool results the model saw, after truncation.

## By arm

raw: the API as is, one tool per endpoint. shaped: the plan's task-shaped tools, every field kept. lean: shaped plus the plan's drops and extracts.

| Arm | Pass | wrong_fit | missed_flag | bad_json | stopped | Median tokens in | Median tool chars | Median calls | Fallback calls | Truncations |
|---|---|---|---|---|---|---|---|---|---|---|
| raw | 18/20 | 1 | 1 | 0 | 0 | 3996 | 12452 | 1 | 0 | 0 |
| shaped | 18/20 | 1 | 1 | 0 | 0 | 4190 | 12452 | 1 | 0 | 0 |
| lean | 17/20 | 2 | 1 | 0 | 0 | 1566 | 1634 | 1 | 0 | 0 |

## Savings

Only on tasks both arms passed, so a cheap failure can't look like a saving.

- lean vs raw (n=16): median tokens in 3950 -> 1560 (2.5x fewer)
- shaped vs raw (n=18): median tokens in 3996 -> 4190 (no saving)
- lean vs shaped (n=16): median tokens in 4144 -> 1560 (2.7x fewer)

## Extraction (one-time precompute)

50 items: 50 extracted, 0 cached, 0 failed, 0 empty. 4 quotes unverified and withheld. 2004s total.

## Where lean and raw disagree

### anthropic-5098025008: raw pass, lean missed_flag
- raw: `{"fit":"no","red_flags":[{"type":"seniority","quote":"Staff Software Engineer"},{"type":"experience_inflation","quote":"10+ years of software engineering experience"},{"type":"hours_996","quote":"thrive in high-intensity environments with fast iteration cycles"}]}`
- lean: `{"fit":"no","red_flags":[{"type":"seniority","quote":"We're looking for a Staff Software Engineer to set technical direction at the intersection of engineering and research on the Claude Code team."}]}`

### figma-5691911004: raw pass, lean wrong_fit
- raw: `{"fit":"yes","red_flags":[]}`
- lean: `{"fit":"no","red_flags":[{"type":"seniority","quote":"This opportunity applies to openings at varying seniority levels across our teams"}]}`

### vercel-5752684004: raw missed_flag, lean pass
- raw: `{"fit":"no","red_flags":[{"type":"seniority","quote":"As a Senior Forward-Deployed Engineer"}]}`
- lean: `{"fit":"no","red_flags":[{"type":"seniority","quote":"Senior Forward-Deployed Engineer"},{"type":"experience_inflation","quote":"6+ years of software engineering experience"}]}`

