# Results: greenhouse

Agent model `gpt-oss:20b`, run 2026-11-02. Token counts are Ollama's own (`prompt_eval_count`, summed over every turn of a task). Tool chars are characters of tool results the model saw, after truncation.

## By arm

raw: the API as is, one tool per endpoint. shaped: the plan's task-shaped tools, every field kept. lean: shaped plus the plan's drops and extracts. Extra flags: rows whose answer named a flag type the reference didn't (not failed unless it changed the fit verdict).

| Arm | Pass | Pass 95% CI | wrong_fit | missed_flag | bad_json | stopped | Median tokens in | Median tool chars | Median calls | Fallback calls | Truncations | Extra flags |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| raw | 18/20 | 70%–97% | 1 | 1 | 0 | 0 | 4022 | 12452 | 1 | 0 | 0 | 13 |
| shaped | 18/20 | 70%–97% | 1 | 1 | 0 | 0 | 4216 | 12452 | 1 | 0 | 0 | 8 |
| lean | 17/20 | 64%–95% | 2 | 0 | 1 | 0 | 1605 | 1781 | 1 | 0 | 0 | 12 |

## Reliability

Lean failed 2 of the 18 tasks raw passed. These are the mistakes the trimming caused.

- anthropic-5238637008: raw pass, lean wrong_fit. lean: `{"fit":"no","red_flags":[{"type":"experience_inflation","quote":"Minimum years of experience: Years of experience required will correlate with the internal job level requirements for the position"},{"type":"pay","quote":"$300,000–$320,000 USD"}]}`
- figma-5551697004: raw pass, lean bad_json. lean: `{"fit":"no","red_flags":[{"type":"location","quote":"London, England"},{"type":"pay","quote":"pay_range": null}]}`

Both failed: anthropic-5454673008
Lean only: anthropic-5098025008

## Savings

Only on tasks both arms passed, so a cheap failure can't look like a saving.

- lean vs raw (n=16): median tokens in 4022 -> 1598 (2.5x fewer)
- shaped vs raw (n=18): median tokens in 3976 -> 4170 (no saving)
- lean vs shaped (n=16): median tokens in 4216 -> 1598 (2.6x fewer)

## Break-even

One-time extraction cost per posting against tokens and seconds saved per agent query (medians, tasks both arms passed). Different models, so the token figure is a rough guide.

- Extraction per posting: 1986 tokens (gemma4:12b), 28 s. Saved per query: 2424 tokens (gpt-oss:20b), 9.5 s. Break-even after 0.8 queries by tokens, 2.9 by seconds.

## Extraction (one-time precompute)

50 items: 30 extracted, 20 cached, 0 failed, 0 empty. 1 quotes unverified and withheld. 839s total.

## Where lean and raw disagree

### anthropic-5098025008: raw missed_flag, lean pass
- raw: `{"fit":"no","red_flags":[{"type":"seniority","quote":"We’re looking for a Staff Software Engineer to set technical direction at the intersection of engineering and research on the Claude Code team."},{"type":"experience_inflation","quote":"Have 10+ years of software engineering experience, with a track record of operating as a Staff or Principal engineer (or equivalent) at a high-caliber organizat`
- lean: `{"fit":"no","red_flags":[{"type":"seniority","quote":"We're looking for a Staff Software Engineer to set technical direction at the intersection of engineering and research on the Claude Code team."},{"type":"experience_inflation","quote":"Have 10+ years of software engineering experience, with a track record of operating as a Staff or Principal engineer (or equivalent) at a high-caliber organizat`

### anthropic-5238637008: raw pass, lean wrong_fit
- raw: `{"fit":"yes","red_flags":[]}`
- lean: `{"fit":"no","red_flags":[{"type":"experience_inflation","quote":"Minimum years of experience: Years of experience required will correlate with the internal job level requirements for the position"},{"type":"pay","quote":"$300,000–$320,000 USD"}]}`

### figma-5551697004: raw pass, lean bad_json
- raw: `{"fit":"no","red_flags":[{"type":"location","quote":"London, England"}]}`
- lean: `{"fit":"no","red_flags":[{"type":"location","quote":"London, England"},{"type":"pay","quote":"pay_range": null}]}`

