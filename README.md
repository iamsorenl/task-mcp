# task-mcp

Point it at a bloated API, describe the task, and it generates a small MCP server that hands the model only what the task needs. Long text fields (like a job description) get turned into a few checked facts instead of being passed through whole.

**First result, 20 Greenhouse job postings screened by a local `gpt-oss:20b`:** the lean server cut median input tokens from 3,950 to 1,560 (2.5x fewer) and tool output from 12.4k to 1.6k characters. It passed 17/20 tasks against 18/20 for the raw API. So it's cheaper, and slightly less accurate. Full numbers are in [`examples/greenhouse/REPORT.md`](examples/greenhouse/REPORT.md).

Inspired by Nexla's talk "How We Built Agents That Build Task-Specific MCP Servers" (Production Agent Lab, SF, 2026-10-22). Background research is in [`research/`](research/README.md).

## Quickstart

Everything runs on local Ollama models by default (`gpt-oss:20b` for the agent and drafting, `gemma4:12b` for extraction). Python 3.12 and [uv](https://docs.astral.sh/uv/) are required.

```bash
uv sync
# 1. sources.yaml says which endpoints to call; record saves real responses
uv run task-mcp record examples/greenhouse
# 2. a model drafts plan.proposed.yaml: which fields to keep, extract, or drop
uv run task-mcp propose examples/greenhouse --task "Screen job postings for fit against my preferences."
# 3. read what the plan keeps and drops, with token estimates; edit it, save as plan.yaml
uv run task-mcp review examples/greenhouse --plan plan.proposed.yaml
# 4. generate the server
uv run task-mcp build examples/greenhouse --out ~/.task-mcp/greenhouse
claude mcp add greenhouse-lean -- uv run --project "$PWD" python ~/.task-mcp/greenhouse/server.py
```

To draft with Claude on your subscription instead of a local model, add `--provider claude-code` to `propose`. It runs `claude -p` with no tools, no MCP servers and an empty working folder, since the prompt carries untrusted API text.

If the plan dropped something the model ends up needing, every tool takes a `fields` param that returns those raw fields. Each use is logged to `fallback.jsonl` so you can see what to add back.

## How it's measured

`precompute`, `eval` and `report` run the same tasks through three versions of the API:

- **raw**: the API as is, one passthrough tool per endpoint.
- **shaped**: the plan's task-shaped tools and filters, but every field kept.
- **lean**: the full plan, with drops and extracts.

The agent answers each task with JSON (`fit` plus quoted `red_flags`). A task passes when the fit matches the hand-checked answer and every expected red flag is found. Savings only count tasks both arms passed, so a cheap failure can't look like a saving.

The tool reports tokens, not dollars, on purpose. [arXiv 2607.12161](https://arxiv.org/abs/2607.12161) found a 38% cut in tool-output tokens raised billed cost 6.8%, because prompt caching dominates the bill. Here every token is local, so there's no bill to report, only fewer tokens and less time.

## What I learned

- **Field trimming mattered here; tool shape didn't.** shaped vs raw saved nothing, because the raw API already answered in one call. Nexla's wins came mostly from fewer calls. On an API where the agent needs several calls per task, shape should matter more.
- **Extraction is where the misses come from.** Of lean's three failures, one missed a "high-intensity environments" long-hours flag that the extractor didn't surface, and one quoted a generic "varying seniority levels" line as a red flag. Raw saw the whole text and got both.
- **Extraction is the slow part.** About 40 s per posting on `gemma4:12b`, once, cached by a hash of the text. 50 postings took 33 minutes. Turning off gemma4's thinking mode was what made it usable at all.
- **The local model can draft a plan, but not a good one.** `gpt-oss:20b` wrote a valid plan in about a minute, but put the description extract on the search tool, which would extract every posting on every search (about 111k est tokens per search vs about 180 for the hand-written plan). The eval uses the hand-written `examples/greenhouse/plan.yaml`. That's what the review step is for.
- **Quotes are checked.** Every quote the extractor returns must appear in the source text after normalizing. Across 50 postings, 4 quotes failed and were withheld from the model.

## Pointing it at another API

Nothing in `src/` knows about jobs or Greenhouse (a test enforces it). Write a `sources.yaml` for the endpoints and a `tasks.yaml` with checked answers, then follow the quickstart. `examples/github/` is a second, smaller example.

## License

MIT
