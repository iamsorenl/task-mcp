# Results: greenhouse-holdout

Agent model `gpt-oss:20b`, run 2026-11-02. Token counts are Ollama's own (`prompt_eval_count`, summed over every turn of a task). Tool chars are characters of tool results the model saw, after truncation.

## By arm

raw: the API as is, one tool per endpoint. shaped: the plan's task-shaped tools, every field kept. lean: shaped plus the plan's drops and extracts. Extra flags: rows whose answer named a flag type the reference didn't (not failed unless it changed the fit verdict).

| Arm | Pass | Pass 95% CI | wrong_fit | missed_flag | bad_json | stopped | Median tokens in | Median tool chars | Median calls | Fallback calls | Truncations | Extra flags |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| raw | 20/30 | 49%–81% | 9 | 1 | 0 | 0 | 3721 | 10689 | 1 | 0 | 0 | 16 |
| shaped | 21/30 | 52%–83% | 7 | 2 | 0 | 0 | 3915 | 10689 | 1 | 0 | 0 | 14 |
| lean | 20/30 | 49%–81% | 9 | 1 | 0 | 0 | 1577 | 1547 | 1 | 0 | 0 | 16 |

## Reliability

Lean failed 2 of the 20 tasks raw passed. These are the mistakes the trimming caused.

- anthropic-5364804008: raw pass, lean wrong_fit. lean: `{"fit":"no","red_flags":[{"type":"seniority","quote":"Minimum years of experience: Years of experience required will correlate with the internal job level requirements for the position"},{"type":"experience_inflation","quote":"Minimum years of experience: Years of experience required will correlate with the internal job level requirements for the position"}]}`
  - extract: experience_inflation "Minimum years of experience: Years of experience required will correlate with the internal job level requirements for the position"
  - lean repeated the extract's flag
- scaleai-4673771005: raw pass, lean wrong_fit. lean: `{"fit":"no","red_flags":[{"type":"experience_inflation","quote":"At least an active secret clearance and the ability & willingness to up level to TS/SCI with CI Poly."}]}`
  - extract: experience_inflation "At least an active secret clearance and the ability & willingness to up level to TS/SCI with CI Poly."
  - lean repeated the extract's flag

Both failed: anthropic-5057647008 (from extract), anthropic-5437172008 (from extract), anthropic-5462972008 (from extract), scaleai-4513943005, scaleai-4665557005 (from extract), scaleai-4720573005, vercel-6225825004, verkada-5275159007 (from extract)
Lean only: anthropic-5450099008, xai-5111374007

## Savings

Only on tasks both arms passed, so a cheap failure can't look like a saving.

- lean vs raw (n=18): median tokens in 3552 -> 1586 (2.2x fewer)
- shaped vs raw (n=17): median tokens in 3503 -> 3697 (no saving)
- lean vs shaped (n=18): median tokens in 3696 -> 1589 (2.3x fewer)

## Break-even

One-time extraction cost per posting against tokens and seconds saved per agent query (medians, tasks both arms passed). Different models, so the token figure is a rough guide.

- Extraction per posting: 2033 tokens (gemma4:12b), 44 s. Saved per query: 1965 tokens (gpt-oss:20b), 12.2 s. Break-even after 1.0 queries by tokens, 3.6 by seconds.

## Extraction (one-time precompute)

30 items: 30 extracted, 0 cached, 0 failed, 0 empty. 0 quotes unverified and withheld. 1312s total.

## Where lean and raw disagree

### anthropic-5364804008: raw pass, lean wrong_fit
- raw: `{"fit":"yes","red_flags":[]}`
- lean: `{"fit":"no","red_flags":[{"type":"seniority","quote":"Minimum years of experience: Years of experience required will correlate with the internal job level requirements for the position"},{"type":"experience_inflation","quote":"Minimum years of experience: Years of experience required will correlate with the internal job level requirements for the position"}]}`

### anthropic-5450099008: raw wrong_fit, lean pass
- raw: `{"fit":"yes","red_flags":[]}`
- lean: `{"fit":"no","red_flags":[{"type":"experience_inflation","quote":"5+ years of experience as a Data Engineer, Analytics Engineer or in a similar role"}]}`

### scaleai-4673771005: raw pass, lean wrong_fit
- raw: `{"fit":"yes","red_flags":[{"type":"other","quote":"At least an active secret clearance and the ability & willingness to up level to TS/SCI with CI Poly. This is a requirement and candidates will not be considered who do not hold at least a secret clearance"}]}`
- lean: `{"fit":"no","red_flags":[{"type":"experience_inflation","quote":"At least an active secret clearance and the ability & willingness to up level to TS/SCI with CI Poly."}]}`

### verkada-5275159007: raw wrong_fit, lean missed_flag
- raw: `{"fit":"yes","red_flags":[{"type":"hours_996","quote":"flexible work schedule—mornings, nights, and unexpected calls/messages may be required to ensure coverage"}]}`
- lean: `{"fit":"no","red_flags":[{"type":"hours_996","quote":"Flexible work schedule\u2014 mornings, nights, and unexpected calls/messages may be required to ensure coverage"}]}`

### xai-5111374007: raw missed_flag, lean pass
- raw: `{"fit":"no","red_flags":[{"type":"seniority","quote":"Sr. Software Engineer, Multimodal Understanding"},{"type":"experience_inflation","quote":"Sr. Software Engineer, Multimodal Understanding"}]}`
- lean: `{"fit":"no","red_flags":[{"type":"seniority","quote":"SR. SOFTWARE ENGINEER, MULTIMODAL UNDERSTANDING"},{"type":"hours_996","quote":"Proactive self-starter who thrives in high-intensity environments and is passionate about pushing multimodal AI frontiers"}]}`

