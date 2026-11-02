# task-mcp M2a: make lean as reliable as raw

Builds on M1 (spec `2026-10-29-task-mcp-design.md`, results `examples/greenhouse/REPORT.md`).

## Why

task-mcp cuts the tokens an agent spends reading API responses. M1 showed lean used 2.5x fewer
tokens than raw (1,560 vs 3,950 median) but got 17/20 against raw's 18/20, on 20 tasks, so the
saving can't be trusted yet. Soren's order: **reliable first, savings second.** M2a makes the
trimming trustworthy. M2b (a multi-call API, likely GitHub issues) tests the "fewer calls" saving
later and is out of scope here.

## What went wrong in M1 (from the cache and recordings)

Three lean tasks were mistakes the extractor caused:
- **anthropic-5098025008, missed flag.** The posting says "Thrive in high-intensity environments"
  and "where intensity and technical excellence are the norm". The cached `red_flags` hold only one
  seniority quote. `plan.yaml` defines hours_996 as "996 or long hours", and soft pace words don't
  read as that to gemma4:12b. Explicit wording ("weekends", "extended hours", "long days") was
  caught in every posting that had it.
- **figma-5691911004, over-flag.** "can be held from one of our US hubs or remotely" was flagged as
  location. A remote option is not a limit.
- **anthropic-5454673008, over-flag.** "4+ years" was flagged as seniority; Soren's limit is 4 or
  less, so it's fine.

## Finish line (Soren agreed)

**Lean causes no mistakes raw wouldn't have made.** A caused mistake is a task raw passes and lean
fails (missed flag or wrong fit). Target: 0 or 1 caused mistakes on the held-out set. Over-flags
count as mistakes as much as misses, because either changes the decision Soren would act on.
Tasks lean wins and raw loses are reported but don't offset losses.

Grading stays as in M1 (`grade.py`: fit verdict + recall of expected flag types), so M1 and
M2a numbers compare directly. An over-flag counts when it flips the fit verdict, which is the
decision Soren acts on; both M1 over-flags did. Extra flags that leave fit unchanged are reported
in their own column, not failed. (Claude's call, settled after the builder check.)
Tasks where both arms fail are listed too, marked when lean's failure traces to the extract.

Savings are reported second: median tokens in on tasks both arms passed, as in M1.

## Goals

1. **Fix the extractor** for the three failure kinds above.
2. **Held-out test:** tune only on the 20 M1 tasks; score on ~30 new postings never used for tuning.
3. **Report reliability honestly:** per-arm pass rate with a 95% Wilson interval, the caused-mistake
   count with each case quoted (extract next to the posting sentence), and the token ratio.
4. **Break-even line:** how many agent queries per posting before the one-time extraction pays for
   itself. Precompute records extractor tokens (Ollama `prompt_eval_count` + `eval_count`) next to
   seconds; today it only has seconds. The report gives break-even in tokens and in seconds, and
   labels that extraction tokens are gemma4:12b while saved tokens are gpt-oss:20b. Never dollars.

## Non-goals

- No new API (that's M2b), no extra agent models, no dollar costs.
- No change to the agent model (gpt-oss:20b) or the extractor model (gemma4:12b), so the
  comparison with M1 stays clean. A bigger extractor is a fallback only if the fixes fail, and
  would be reported as a separate result.

## Anti-goals

- Tuning on the held-out postings. Once the held-out set is scored, fixes made afterward need a
  fresh held-out set or must be reported as tuned.
- A keyword pass hardcoded for jobs. task-mcp is a general generator; the fix lives in the plan.
- Hiding a loss. If lean still causes mistakes, the report says so and quotes them.

## The extractor fix (Claude's call, open to change)

- **Plan-configured keyword hints.** A quote list field in an extract schema can declare
  `hints: {<enum type>: [regex, ...]}`. Before the model call, the extractor finds sentences
  matching each regex and passes them to the model as candidates ("these sentences may be
  <type> flags; include each one that is, with the exact quote"). The model still decides; hints
  only stop it overlooking the sentence. For greenhouse, hours_996 hints cover intensity, weekends,
  evenings, extended/long hours, on-call, 996.
- **Sharper descriptions in `examples/greenhouse/plan.yaml`:** spell out soft pace language for
  hours_996; state that a remote or hub option is not a location limit and that years at or under
  the stated limit are not seniority flags.
- The extractor never sees Soren's preferences today. Builder may pass the task file's
  preferences into the extract instructions if the above isn't enough; say so in the report if used.
- **Cache:** the cache key is the text hash only, so a prompt or schema change silently reuses old
  extracts. Include a hash of the extract config (instructions + schema + hints) in the key.

## Pace boundary (Soren decided)

- **hours_996 flag:** "high-intensity", "intensity is the norm", weekends, evenings, extended or
  long hours, 996.
- **Not a flag:** "fast-paced" on its own, a normal on-call rotation.

Refined by Soren while checking the held-out answers (2026-11-02), after the plan was frozen:
"mornings, nights, and unexpected calls" is long hours; late evenings during escalations are
expected (not a flag); a values line like "We value intensity, pace, curiosity" is not long hours.
The frozen plan was not changed. Both affected postings fail fit on years or seniority anyway,
so an over-flag there shows only in the extra-flags column.

This rule drives the hint regexes, the hours_996 description, and the drafted expected answers.

## Held-out set

- ~30 new postings, chosen on purpose, not at random:
  - ~10 with hours or pace wording, some of it benign ("fast-paced", "on-call rotation"), so
    over-flagging is tested too;
  - ~10 near Soren's limits: "4+ years", hybrid or remote options, borderline titles;
  - ~10 ordinary controls.
- Drawn partly from new Greenhouse company boards, partly from anthropic/figma/vercel postings not
  in the M1 set.
- Claude drafts expected answers (fit + red flag types + why); **Soren hand-checks all ~30**
  (agreed), blocking step before the held-out eval, same as M1's Task 11: drafts go in the
  holdout `tasks.yaml` with `checked: false`, Soren edits and flips them. Recording and drafting
  happen first so the wait only blocks the final eval.
- Lives in its own folder (e.g. `examples/greenhouse-holdout/`) with its own sources.yaml and
  recordings, so re-recording never touches the M1 recordings the tuning set depends on.

## If the held-out set fails

If the held-out eval shows 2+ caused mistakes, M2a stops and the report says so, quoting each
case. Further fixes are a new round with a fresh held-out set, not part of M2a. (Claude's call.)

## Runs

- Tuning loop: change extractor, re-extract only the 20 M1 postings, eval only the affected arms
  and tasks, repeat. Full M1 precompute (33 min) and eval (1 hr) rerun once at the end, since the
  extractor changed.
- Held-out: one precompute + one eval of all three arms, once, after tuning is frozen.
- Local Ollama only. No API spend.

## Constraints (from Soren)

- Local Ollama by default; Claude only through `claude -p` on the subscription.
- Commit or push only when Soren asks; branch first if on main (`m1` is still an open PR).
- Report honestly, even when lean loses; tokens, not dollars.
- Keys only in a gitignored .env (none needed for M2a).

## Left to the builder

- Exact hint regexes and prompt wording, and whether hints feed the prompt or post-check the reply.
- Which new boards to record and how to page past `max_details` to find the target postings.
- Report layout for the new sections, and where the break-even numbers come from in code.
- Whether M2a branches off `m1` or waits for PR #1 to merge.
