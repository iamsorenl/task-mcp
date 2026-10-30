# task-mcp: generate lean, task-specific MCP servers from bloated APIs

Date: 2026-10-29
Status: design for Soren's review. Nothing built.
Working name: `task-mcp` (final name picked at review; the repo is created under that name).
Research behind it: `../../../research/01-04*.md` and `../../../README.md` in this folder.

## Why

At Production Agent Lab (2026-10-22, SF), Nexla showed MCP Studio: an agent that builds small,
task-shaped MCP servers instead of one tool per API endpoint. Their published wins come mostly
from fewer turns and calls, not from trimming what each call returns. Soren wants to build his
own version, to learn how this works and to have something he actually uses.

The piece nobody seems to do (research 03, "gaps"): look inside an API's long free-text fields,
design a task-specific extraction for them, generate a server that serves the extract, and
prove the extract doesn't change the agent's answers. Nexla doesn't do the "inside a field" part
publicly. Existing trimmers use hand-written filters or have the model write a jq filter on every call.

Job boards show the problem clearly (measured 2026-10-29):
- Greenhouse `boards/anthropic/jobs?content=true` returns 673 jobs in one response, about 9M
  characters (well over 2M tokens). No model can take that in.
- One Greenhouse posting is about 13.4k chars raw. HTML-to-text and dropping metadata get it to
  about 8.5k. The description is still almost all of it, and pay is buried inside it.
- Lever returns each description twice (HTML and plain text).

## What success looks like

1. **A demo:** point the CLI at an API, describe a task in a sentence, approve a plan, and watch
   an agent using the generated server reach the same answers as with the raw API, using a
   fraction of the tokens.
2. **Real use:** Soren keeps using the generated job server to screen roles.
3. **General from day one:** jobs are the first example and test case. Nothing in the generator
   knows about jobs. Someone else can point it at their API with their task. Being rough early is
   fine: it's open source and gets fixed in the open.

## Goals

- A CLI that goes from an API to a working MCP server through: record, propose, review, build, eval.
- **Tool shaping** (the Nexla lesson): propose a few task-shaped tools, not one tool per endpoint.
  For jobs, that's a search tool returning short rows and a detail tool for shortlisted roles.
- **Field decisions:** each response field gets keep, drop, or extract. Each decision gets a
  one-line reason the human can read.
- **Extraction of long text fields** into a task-specific schema the model proposes and the human
  approves.
- **A human review step** before anything is generated, editable as a plain file.
- **A fallback:** the generated server lets the model ask for a dropped field by name, so a bad
  trim can be recovered instead of being silently wrong. Fallback calls get logged.
- **An eval** that proves the trim is safe and measures how much it saves.
- **Free by default:** local models through Ollama. Claude only behind an explicit flag.

## Non-goals (v1)

- Learning from fallback logs to update the plan automatically. That's v2. v1 only writes the log
  in a format v2 can use.
- A web UI, hosting, auth flows, or write/mutation endpoints. v1 is read-only GET APIs, public or
  API-key auth.
- Beating Nexla on their benchmarks, or claiming dollar savings. The cost paper (arXiv 2607.12161)
  showed token cuts can raise the bill once prompt caching is counted. Report tokens and calls
  honestly. Add billed cost only if the Claude provider is used, and label it.

## Anti-goals (would make it a failure even if it runs)

- **A trim that changes answers.** It saves 90% of tokens but the agent calls a role a fit when the
  full posting says Staff-level, 5 days in NYC, or 996. A missed red flag counts as a failure even
  if the overall fit verdict happens to match.
- **Made-up extracted facts.** Every extracted red flag and experience requirement carries the
  exact source sentence. The eval checks that the quote appears in the original text.
- **Job logic in the generator.** If supporting a second API needs code changes in the core, the
  design failed.
- **Surprise spend.** No paid API call without the flag.

## The flow

```
record   ->  propose  ->  review  ->  build  ->  eval
samples      plan.yaml    you edit     server     raw vs lean report
```

1. **record:** the input is an OpenAPI spec if there is one, otherwise a small YAML listing
   endpoints (URL template, params, auth env var). Greenhouse and Lever have no spec. It calls each
   endpoint with a few seed params (e.g. 3-5 board tokens) and saves the raw responses to disk.
   Everything after this runs offline from recordings, so runs are repeatable.
2. **propose:** given the recordings and a task sentence ("screen job postings for fit against my
   preferences"), a model drafts `plan.yaml`. The plan covers:
   - the tools to expose, each with a name, description, params, and the source endpoint(s) it uses;
   - for every field path: keep / drop / extract, with a one-line reason;
   - for each extract field: an output schema, and which items must carry source quotes;
   - estimated tokens per tool call before and after, computed from the recordings.
3. **review:** the CLI prints a readable summary of the plan. The human edits `plan.yaml` directly
   (flip a field, rename a tool, change the extract schema). `review` re-validates the file and
   re-estimates tokens. The plan is the source of truth; build only reads the plan.
4. **build:** generates a standalone Python FastMCP server package from the plan. At runtime it:
   - calls the live API, applies the keep/drop rules and HTML-to-text, and runs extraction on
     extract fields;
   - caches each extraction on disk, keyed by item id plus a hash of the source text, so a changed
     posting gets re-extracted and an unchanged one never does;
   - exposes the fallback: an optional `fields` param on each tool, or a `get_field(item, path)`
     tool (builder's call), returning dropped fields raw and logging the request to a JSONL file.
5. **eval:** see below.

### Job example: what the plan should come out roughly like

This is the expected result for the demo, not hardcoded logic.
- `search_jobs(board, query?, location?)`: returns rows of id, title, location, department, url.
- `get_job(board, id)`: returns title, location, pay range, plus the extract of the description:
  - **scope:** one or two sentences on what the role owns;
  - **day to day:** a short list of what the time goes to;
  - **experience asked:** years, plus seniority words verbatim, with source quotes;
  - **red flags:** inflated requirements, 996 or long-hours language, anything else off, each
    with a source quote;
  - **pay range** parsed from the text, and **onsite terms** including days per week.
- Dropped: company blurb, benefits, EEO text, how-to-apply, internal ids, compliance metadata,
  duplicate HTML/plain copies.

Soren's own screening preferences (no 996, Bay Area only, skip Senior/Staff, SF/Peninsula onsite
is fine) live in the **eval task config**, not in the server. The server extracts facts. The agent
applies preferences.

## Eval

The eval answers two questions: is the lean server safe, and how much does it save.

**Three arms, same model, same tasks, all from recordings:**
- **raw:** a generated passthrough server, one tool per endpoint, returning raw JSON. Responses
  over the model's context window are truncated the way a naive client would, and that's recorded.
- **shaped:** the plan's tools with all fields kept. This isolates the Nexla-style
  tool-shaping win.
- **lean:** shaped plus drop and extract. Lean minus shaped gives the extraction win, which is the
  novel part.

**Tasks** come from a task file the user writes per API. For jobs, a task looks like: "Here are my
preferences. Is this role a fit, and what red flags does it have?" The task file holds the
preferences, the postings, and the expected answers.

**Reference answers.** Soren agreed to hand-check postings. Claude picks about 20 (including
known red flags) and drafts the answers. Soren confirms or fixes them, about 20-30 minutes, as a
blocking step before the eval milestone. The eval harness is built against stub labels until
then. Each posting gets a verdict
from a reference model reading the full posting text. On top of that, there's a hand-checked set
of about 20 postings that Soren confirms. It includes some with known red flags, for example a
real posting with 996 or "high-intensity" language, a Staff title, or NYC-only. The hand-checked
set is the guardrail. The reference-model set gives volume.

**Metrics per arm:**
- task success (fit verdict matches);
- red-flag recall (every reference red flag found);
- quote validity (extracted quotes appear in the source);
- input tokens per task and tool-result tokens;
- tool calls and turns;
- fallback-call rate, which directly signals a field the trim should have kept;
- wall time, including one-time extraction time (judgelab measured gemma4:12b at about 30s per
  posting, so extraction cost is reported separately from serving cost).

Report savings only on tasks both arms solved, so a lean arm that "saves" tokens by failing
doesn't look good.

**Output:** a `REPORT.md` with an arm-by-metric table and the worst disagreements quoted. A
disagreement is a posting where lean and raw disagree, shown with the extract next to the
original text.

**Reuse:** the Ollama tool-calling loop, the replay of recorded calls, and the report style come
from `~/Desktop/Active Projects/mcp-modelcheck` (`agent.py`, `replay.py`, `report.py`). Soren's
call: this is its own repo, and mcp-modelcheck is effectively its eval half. Builder's call:
depend on it as a git dependency or vendor the few files. Either way, token counting gets added
since mcp-modelcheck doesn't count tokens today.

## Constraints

- Python, uv, MIT license. Public repo `iamsorenl/<name>`, created once the name is picked.
- **Claude without API credits (Soren's call):** a third provider, `--provider claude-code`,
  shells out to `claude -p --output-format json`. It runs on Soren's Claude subscription login,
  not API credits. It's used only for the one-time propose step when the local plan isn't
  usable. Agent runs and extraction stay local. Other users of the open-source tool pick Ollama,
  their own Claude Code login, or an API key. The tool never asks for or stores anyone's
  claude.ai login itself.
- Models: Ollama by default. The default model is the one mcp-modelcheck found best at tool
  calling (gpt-oss:20b), with the extraction model configurable separately. Claude via
  `--provider anthropic`, with the key from env or a gitignored `.env`.
- `pytest` passes with no model running: fake chat function, recorded fixtures (the
  mcp-modelcheck pattern).
- Token counts are labeled with their tokenizer. Ollama reports real counts per call. The Claude
  path uses API `usage`. Offline estimates are labeled as estimates.
- Recordings of public job boards are fine to commit. Anything keyed stays out of git.

## Decided by Soren

- The generator is general from the start; jobs are the first example.
- Local models by default, Claude supported.
- Human review before build.
- v1 job fields: title, description (extracted), location, pay. The extract covers scope, day to
  day, experience, and red flags including 996 and hours.
- This is its own repo, and mcp-modelcheck is the eval half.
- The demo matters most, then real utility.

## Calls I made (Claude), open to change

- The CLI verbs, `plan.yaml` as the single editable source of truth, and FastMCP for generated
  servers.
- The three-arm eval (raw / shaped / lean), and reporting savings only on tasks both arms solved.
- Caching extraction keyed by id plus content hash.
- Read-only GET and API-key auth only in v1.
- First sources: public Greenhouse, Lever, and Ashby boards.

## Settled after the builder check (Claude's calls, open to change)

- **How eval replays:** the generated server runs for real during eval, but its HTTP layer is
  swappable. In eval it reads recorded raw responses keyed on method+URL+params, so there's no
  live API call. The recorder keys on URL+params. Tool-level filtering, such as `search_jobs(query,
  location)` over a board that returns everything, happens inside the generated server. The plan
  says which field each filter param matches, as a case-insensitive substring by default. The raw
  arm replays the same recordings through a passthrough server. Extraction runs once in a
  `precompute` step that fills the cache, and eval reads the cache. Extraction time is reported
  from that step.
- **Grading:** the agent's final answer is structured JSON: `{"fit": "yes|no|maybe",
  "red_flags": [{"type": ..., "quote": ...}]}`. Red-flag types come from a fixed list in the task
  file (for jobs: `seniority`, `experience_inflation`, `hours_996`, `location`, `pay`, `other`).
  Recall matches on type. A bad JSON answer counts as a failed task. There's no LLM judge.
- **Quotes:** "must carry a source quote" is a generic schema annotation (`quote: true`).
  Validation is a substring check after normalizing whitespace, case, and HTML entities. When a
  quote fails, the server drops that item, adds it to an `unverified` list in the response, and
  counts it. It never returns an unverified quote as fact.
- **Field paths:** a JSONPath subset (`a.b`, `a[*].b`). Keep/drop/extract rules apply per path,
  including inside arrays. A tool can use two endpoints when the plan maps a list item's field
  into the detail endpoint's URL template (e.g. `id` into `/jobs/{id}`). That's generic
  templating, not job logic.
- **Generality test:** GitHub issues (`samples/gh_issues.json`) is the second API, as a fixture in
  the test suite. If supporting it requires changes to the core, the anti-goal is broken.
- **First milestone:** the demo path on Greenhouse only (record, propose, review, build,
  precompute, eval), run locally. Lever, Ashby, and the Claude provider come after.
- **Generated server packaging:** it imports a small runtime module from this package (cache,
  quote check, HTTP backend, fallback log), so it needs `task-mcp` installed. It is not vendored.
- **Model defaults:** the agent and propose steps use gpt-oss:20b, and extract uses gemma4:12b
  (WarmPath's judge model). All three are configurable separately.

## Left to the builder

- Package layout, prompt wording, the HTML-to-text library, and the YAML schema details.
- The fallback shape (`fields` param vs a `get_field` tool).
- How the propose step handles very large responses: sample a few items from a big list rather
  than feeding the whole list to the model.
- Git dependency vs vendoring mcp-modelcheck pieces.
