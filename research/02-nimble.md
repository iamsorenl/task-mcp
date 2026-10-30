# Nimble (nimbleway.com): how its agent-facing tools shape output for LLMs

Researched 2026-10-26. Every claim has a URL or a repo path. "(inferred)" marks my own reading, not a stated fact.
Local clones used for line refs: `/private/tmp/claude-503/-Users-Soren/a8119ac8-d7ae-4de2-b680-af5846e3df04/scratchpad/n/{agent-skills,cookbook,nimble-cli}` (shallow clones of main, 2026-10-26).

## 0. Headline findings

1. The MCP server is hosted, not open source. I found no MCP server repo in the Nimbleway org (list: `gh repo list Nimbleway`). The endpoint is `https://mcp.nimbleway.com/mcp`. So there is no server code to read for trimming logic. See section 6.
2. Nimble's own docs warn that the MCP route is token-heavy: "MCP routes results through the LLM context window and can consume tokens quickly," and they recommend the CLI skill for typical web retrieval. Source: https://docs.nimbleway.com/integrations/mcp-server/mcp-server.md
3. Their token-saving design is mostly "keep big payloads out of the context window": the CLI writes to files and the agent reads slices. That is a client-side pattern, not a server-side trim. See section 3.
4. Server-side shaping happens through a few knobs: search depth (lite, fast/standard, deep), `output_format`, `formats: markdown`, CSS-selector `parser` schemas, Extraction Templates with typed `output_schema`, and Web Search Agents with `output_schema` plus citations. Section 2.
5. The one number Nimble publishes is "51% fewer tokens per query" for Web Search Agents. It is vendor-supplied, with no published methodology. Section 5.

## 1. Product map (agent-facing)

| Product | What it is | Source |
|---|---|---|
| MCP server | Hosted Streamable HTTP, OAuth 2.1 + PKCE or Bearer API key. Tools prefixed `nimble_`. Groups: Search, Extract, Map, Crawl, Extract Template, Agent. | https://docs.nimbleway.com/integrations/mcp-server/mcp-server.md ; `agent-skills/AUTH.md` ; `agent-skills/.mcp.json` |
| Search API | `POST https://sdk.nimbleway.com/v1/search`. Depth and focus modes. | https://docs.nimbleway.com/nimble-sdk/web-tools/search.md ; `cookbook/apps/competitor-intelligence-monitor/agent/agent.py:100-122` |
| Extract API | URL to HTML and/or markdown, optional JS render, parsing, network capture. | https://docs.nimbleway.com |
| Map / Crawl | URL discovery and multi-page crawl. | https://docs.nimbleway.com |
| Extraction Templates | Per-site structured scrapers. Run by name with `input_schema` and `output_schema`. $3 / 1K runs. | https://docs.nimbleway.com/nimble-sdk/web-tools/extract/template.md ; `agent-skills/skills/nimble-web-expert/references/nimble-extract-templates/reference.md` |
| Web Search Agents (Agent API V2) | Goal in, discovery + navigation, then text or JSON result with per-claim citations. `POST /v2/agents/*`. | `agent-skills/skills/nimble-web-expert/references/nimble-agents/reference.md` (intro, "Trust & citations") ; https://docs.nimbleway.com/nimble-sdk/web-search-agents/overview.md |
| CLI | `@nimble-way/nimble-cli` (npm), Go, generated SDK-style. | https://github.com/Nimbleway/nimble-cli |
| SDKs | Python, TypeScript, Go. | https://github.com/Nimbleway/nimble-python , https://github.com/Nimbleway/nimble-typescript , https://github.com/Nimbleway/nimble-go |
| Framework integrations | LangChain, LlamaIndex, Vercel AI SDK, Mastra, Cloudflare Agents, MS Agent Framework, Hermes, Vercel Eve. | repo list: https://github.com/Nimbleway |
| Agent skills plugin | Claude Code / Cursor / Codex / Grok plugin: ~30 skills plus the MCP connector. v1.9.0. | https://github.com/Nimbleway/agent-skills (`README.md`) |

The cookbook `nimble-mcp-server` README is stale. It documents an older SSE endpoint (`https://mcp.nimbleway.com/sse`) and four older tools: `nimble_deep_web_search`, `nimble_google_maps_search`, `nimble_google_maps_reviews`, `nimble_google_maps_place` (`cookbook/nimble-mcp-server/README.md:5-10`). Current tool names are in section 6.

## 2. How each surface shapes output for an LLM

### 2a. Search

Parameters (`agent-skills/skills/nimble-web-expert/references/nimble-search/reference.md`, parameter table around lines 27-44):
- `search_depth`: `lite` = metadata only (title, URL, snippet); `fast` = "rich cached content"; `deep` = "full real-time page content". The reference says to prefer `fast` for agents.
- `max_results`: 1-100, default 10.
- `output_format`: `plain_text`, `markdown` or `simplified_html`.
- `include_answer`: AI-synthesized answer, a premium add-on.
- `include_domains` / `exclude_domains`: up to 50 each. `time_range`, `start_date`, `end_date`, `country`, `locale`, `content_type`.
- Response: `results[].title`, `description`, `url`, `content`, `metadata.position`, `metadata.entity_type`, plus optional `answer`. Same file, "Response structure".

Discrepancy between sources. The public docs list only `lite` and `standard` (default) depths plus a `full_content: true` flag that adds scraped page text. The page says focus modes only work with `lite` (https://docs.nimbleway.com/nimble-sdk/web-tools/search.md). The pricing page also lists only lite and standard (https://docs.nimbleway.com/nimble-sdk/admin/pricing.md). The skills repo documents `lite/fast/deep` and a deprecated `deep_search` bool. These look like two API generations. Treat the skills repo as possibly newer or stale (inferred). Check against the live API before relying on either.

The cheapest LLM-friendly mode is `lite`: titles, URLs and snippets only. The cookbook monitor uses `search_depth: "lite"` and then clips fields client-side: `title[:150]` and `description[:250]` (`cookbook/apps/competitor-intelligence-monitor/agent/agent.py:104-110` and `:136-150`). GitHub release bodies are clipped to 300 chars (`agent.py:320`). That is the clearest example of client-side trimming in Nimble's own sample code.

### 2b. Extract

- `formats`: `html` (default) or `markdown`; the CLI has `--format`. `agent-skills/skills/nimble-web-expert/references/nimble-extract/reference.md:38`. The playbook also lists `plain_text` and `simplified_html` (`agent-skills/_shared/nimble-playbook.md`, "Extract" section, around lines 236-256).
- The default is HTML, so an agent must ask for markdown to avoid raw HTML.
- Playbook guidance: markdown gives "clean body content, no nav/footer noise", but it strips `<head>` metadata, JSON-LD and attributes, so use HTML when you need those (playbook "Format selection by use case" table).
- `render` (headless browser), `driver` tiers `vx6` to `vx10-pro`, `is_xhr` (direct API call, no browser), `network_capture`, and browser `actions`. Same extract reference, parameter table lines 36-53.
- Garbage check: if `data.markdown` has under 100 meaningful chars, retry with `--render`. Playbook "Extraction fallback".
- Docs state Extract can return HTML and Markdown plus a parsing object, screenshots and network capture. The docs home page makes no token-savings claim. Source: https://docs.nimbleway.com

### 2c. Parsing ("AI parsing" or not)

`--parse --parser '{...}'` returns structured JSON in `data.parsing`. Per `references/nimble-extract/parsing-schema.md` (schema types, selectors, extractors, post-processors) it is deterministic and declarative:
- CSS, JSONPath and XPath selectors.
- Extractors: `text`, `attr`, `html`.
- Post-processors: `regex`, `number`, `boolean`, `url`, `sequence`.
- Parser types include `schema`, `schema_list`, `terminal`, `terminal_list` and `or` fallbacks.
- Example: `"$1,299"` becomes `1299` via the `number` post-processor.
- The file's own caveat: "Selectors break when page structure changes."

Contradiction inside the same repo. `_shared/nimble-playbook.md` (extract table, around line 256) says `--parse --parser` is "LLM extracts specific fields" and "structured extraction via LLM parser schema". `parsing-schema.md` documents selectors with no LLM. I could not confirm an "AI parsing" mode from the primary docs. Treat the playbook line as unverified. The LLM-driven path appears to be the Web Search Agent (next sections), not `--parser` (inferred).

### 2d. Extraction Templates

Reusable per-site scrapers (Amazon, Reddit, Google Maps and similar). The agent lists, then calls `get` to see `input_schema` and `output_schema`, then runs with `--params`. The response is the template's `output_schema` records: an array for SERP-style templates, an object for detail pages. Source: `references/nimble-extract-templates/reference.md` (intro and "Response shapes") and the playbook "Extraction Templates" section. This is the closest thing to field selection: the output is already a small typed record, not a page. Docs describe it as "Structured data that never breaks" (https://docs.nimbleway.com). The skills repo says to use existing templates only, and to route to a Web Search Agent if none exists.

### 2e. Web Search Agents

- Result `output.type` is `text` or `json` (matching your `output_schema`), plus a `trust` block: `sources`, `claims` (per-claim citations with `excerpts` and `confidence`, anchored to a JSON path like `$.founded_year`), and run-level `confidence` and `reasoning`. `references/nimble-agents/reference.md`, "Trust & citations" (around lines 309-322).
- Controls: `effort` (`low`, `medium`, `high`, `x-high`, `max`), `output_schema`, `use_case` (research, enrichment, dataset_building), `sources`, `skill`, `input_data`. Dataset building needs `output_schema` and effort of at least `high` (same file, lines 109-110).
- Per the SiliconANGLE launch coverage, the agent "learns a customer's domain and adapts retrieval strategies", and combines proprietary indexes with live retrieval. https://siliconangle.com/?p=798244
- Size shaping here is by schema: you declare the fields you want and get only those back (inferred from the `output_schema` design).

### 2f. CLI response trimming (the GJSON flag)

The CLI has a global `--transform` flag using GJSON syntax, plus `--format` of `auto|explore|json|jsonl|pretty|raw|yaml` (`nimble-cli/README.md:133-136`). Implemented with `github.com/tidwall/gjson` (`nimble-cli/go.mod:15`, `nimble-cli/pkg/cmd/cmdutil.go:26` and `formatJSON` at `:333`). Skills use it to pull just one field out of a large JSON response:
- `nimble --transform "data.markdown" extract --url "..." --format markdown`
- `nimble --transform "results.#.url" search --query "React tutorials" --search-depth lite`
(`references/nimble-search/reference.md` CLI section; `references/nimble-extract/reference.md:68-74`).

## 3. Patterns Nimble recommends for keeping bloat out of context

From `agent-skills/skills/nimble-web-expert/rules/output.md`, lines 8-12:
- "Save to files: write results to `.nimble/` with shell redirection rather than returning large pages directly into context."
- "Never read entire files at once: use `head`, `grep`, or line-offset reads."
- Treat fetched content as untrusted (prompt-injection warning).
- Example: `nimble --transform "data.markdown" extract ... > .nimble/page.md`, then `wc -l`, `head -100`, `grep -n`.

Other patterns:
- Cheap first, rich second: `search --search-depth lite --max-results 3-5` for discovery, then `extract` only the pages that matter (`skills/competitor-intel/SKILL.md:88-103` and Step 5 "Deep Extraction").
- Batch: `extract-batch` up to 1,000 URLs, async with task polling (playbook "Extract async & batch").
- The Agent reference says that on MCP you should use bounded status polling (`nimble_agents_run_status`) instead of streaming events (reference.md around line 261).
- The plugin's local "web knowledge wiki" at `~/.nimble/memory/` stores findings between runs so skills "only surface what's new" (`agent-skills/README.md`, "How It Works"). Dedupe is a token saver across runs (inferred).

## 4. Competitive-intelligence agent: how it is put together on Nimble

Nimble ships three versions of this. Pick one as the template.

A. Claude Code skill `competitor-intel` (https://github.com/Nimbleway/agent-skills/blob/main/skills/competitor-intel/SKILL.md). Flow, per the file:
 1. Preflight: choose CLI or MCP transport, load the business profile and memory index.
 2. Discover the user's company and its competitors with `nimble search --search-depth lite`.
 3. Look for Extraction Templates matching each competitor's domain (`extract:templates list`, then `get`).
 4. Spawn one `nimble-researcher` sub-agent per competitor in parallel. About 6 searches per competitor (news, launches, hiring, funding). With 2 or more competitors, use `extract-batch`.
 5. Deep-extract the signals that need date verification (`extract --format markdown`).
 6. Drop stale items, verify the real event date, compare with the previous run, and write the report with source URLs.
 7. A `nimble-analyst` agent does cross-competitor synthesis.
 Related skills: `competitor-positioning`, `launch-monitor`, `brand-mention-monitor`, `company-deep-dive`.

B. Python cookbook `competitor-intelligence-monitor` (https://github.com/Nimbleway/cookbook/tree/main/apps/competitor-intelligence-monitor). Pipeline: `config.json` lists competitors, `agent.py` fires many Nimble `lite` searches per competitor across Reddit, X, LinkedIn, HN, GitHub, news, blogs, reviews, Product Hunt and YouTube. It clips snippets, then runs one Claude synthesis pass that dedupes, scores impact and flags positioning alerts. It posts to Slack and can be scheduled via GitHub Actions. Search call at `agent.py:104-122`, clipping at `:136-150`, truncation fallback at `:592`.

C. `competitor-battlecard-generator` and other apps in the same cookbook (`cookbook/apps/`): includes `company-event-monitoring-agent`, `gtm-buying-trigger-agent`, `hotel-rate-intelligence`, `live-docs-grounding-agent`.

For the workshop itself (inferred): "Build a Competitive Intelligence Agent with Live Web Data" most likely follows A or B (search, extract, synthesize into a sourced briefing). Luma says participants "gather current competitor information and turn it into a sourced briefing for ongoing research and monitoring." I found no public repo, slides or recording tied to the session.

## 5. Token and cost claims

| Claim | Source | Caveat |
|---|---|---|
| Web Search Agents: "21-point increase in answer quality and 51% fewer tokens spent per query" | https://siliconangle.com/2026/07/29/nimble-launches-web-search-agents-cut-ai-research-token-costs/ ; https://siliconangle.com/?p=798244 | Vendor benchmark. Let's Data Science says the comparison is against ChatGPT 5.5 and Claude Opus 4.8, run by an unnamed customer with no disclosed methodology: https://letsdatascience.com/news/nimble-launches-domain-aware-web-search-agents-63611420 . VentureBeat headline: https://venturebeat.com/orchestration/nimble-claims-its-new-domain-specialized-web-search-agents-cut-token-costs-in-half-while-boosting-retrieval-accuracy |
| Rox (CRM customer): "20-fold reduction in token costs" | https://siliconangle.com/?p=798244 | Single customer quote. |
| Plugin manifest description: "lower token cost per answer" | `agent-skills/CHANGELOG.md:29` | Marketing line, no number. |
| MCP "can consume tokens quickly", CLI skill recommended | https://docs.nimbleway.com/integrations/mcp-server/mcp-server.md | Nimble's own caution against its MCP for normal retrieval. |
| Nimble handles 90M+ searches/day | https://siliconangle.com/?p=798244 | Scale claim, not tokens. |

Nimble publishes benchmark harnesses at https://github.com/Nimbleway/Public-benchmarks: `DRACO-research-benchmark` (100 tasks, rubric-scored on accuracy, depth, presentation, citations) and `SimpleQA-Benchmark` (search-API provider comparison with retrieval quality and latency). `README.md` there. I did not run them, and did not check whether they report token counts.

The docs home and search pages make no token-savings claim for Search or Extract output (checked https://docs.nimbleway.com and the search docs page).

## 6. MCP server: is the code public?

- No. Searches of the org (`gh repo list Nimbleway --limit 50`) show no MCP server repo. `gh search repos "nimble mcp"` returned only third-party hits: `poacosta/decision-bridge-nimble-mcp` (unrelated, an Ollama bridge) and `nimblecrm/nimble-crm-plugin` (a different company, Nimble CRM, not Nimbleway).
- `gh search code --owner Nimbleway "mcp.nimbleway.com"` returns only client config and docs: `agent-skills` (`.mcp.json`, `mcp.json`, `AUTH.md`, README), and `cookbook` (`claude-managed-agents/README.md`, `nimble-mcp-server/*`).
- So I cannot give file and line references for how the server trims or formats responses. What exists is the client-visible contract:
  - Endpoint and config: `agent-skills/.mcp.json` (`type: http`, url `https://mcp.nimbleway.com/mcp`) and root `mcp.json` (`streamable-http`).
  - Tool names, as listed in the skill's `allowed-tools` (`agent-skills/skills/nimble-web-expert/SKILL.md:33-52`): `nimble_search`, `nimble_extract`, `nimble_extract_async`, `nimble_map`, `nimble_crawl_run`, `nimble_crawl_status`, `nimble_crawl_list`, `nimble_crawl_terminate`, `nimble_task_results`, `nimble_extract_templates_list`, `_get`, `_run`, `_run_async`, `nimble_agents_list`, `nimble_agents_get`, `nimble_agent_templates_list`, `nimble_agent_templates_get`, `nimble_agents_run`, `nimble_agents_run_status`. Prefixed `mcp__plugin_nimble_nimble__` in the plugin.
  - Claimed parity: "All CLI commands have MCP equivalents" (`_shared/nimble-playbook.md`, "MCP Fallback", around line 471-477). A few Agent controls are CLI-only (same section).
  - MCP is treated as the fallback transport in skills. CLI is "preferred, full surface area" (`_shared/nimble-playbook.md:22`).
- The MCP docs page does not document parameter schemas, output formats or response-size limits (https://docs.nimbleway.com/integrations/mcp-server/mcp-server.md). Whether the server applies any truncation or markdown conversion is unknown. To find out, call the tools and measure the output.
- The CLI is open source, but it is a generated API client with output formatting (GJSON `--transform`, `--format`). It does no content trimming of its own that I found. https://github.com/Nimbleway/nimble-cli

## 7. Pricing and free tier

Per https://www.nimbleway.com/pricing and https://docs.nimbleway.com/nimble-sdk/admin/pricing.md (successful requests only):
- Free: 5,000 requests or pages per month (marketing page) or "5,000 free web pages" (docs page). No credit card.
- Search lite $1.10 / 1K; Search standard $5.00 / 1K; `full_content: true` adds $1.00 / 1K URLs.
- Extract, Crawl, Map: $1.00 / 1K URLs. File-parsing add-ons: $2.50 / 1K pages (light), $7.50 / 1K pages (pro).
- Extraction Templates: $3.00 / 1K runs (the marketing page adds a 10% managed-service fee).
- Media $2 / GB. Residential proxy $5.30 / GB.
- Agent API, flat per task by effort: low $0.025 (10-30 s), medium $0.10 (1-3 min), high $0.50 (5-15 min), x-high $2.00 (15-30 min), max custom.
- Subscriptions (annual): Startup $2,500/mo (350K pages, 5 concurrent agents), Scale $7,000/mo (1.2M), Professional $15,000/mo (3M), Enterprise custom. MCP integration is listed among plan features.
- MCP use itself is not priced separately in anything I found. It bills as the underlying API calls (inferred).
- The Web Search Agents launch coverage says a free trial is included: https://siliconangle.com/?p=798244

## 8. The workshop and other public material

- Event page: https://luma.com/oct10lab. "Production Agent Lab - Workshop," San Francisco, hosted by tokens&. Workshop listed: "Build a Competitive Intelligence Agent with Live Web Data," led by Amaury Desrosiers (Head of FDE and Director of Solution Consulting at Nimble per the page). Description: "Connect your AI agent to the live web with Nimble." Nimble is a lab partner; Yaniv Markovski and Justus Santiago of Nimble are judges. The page does not list a date, and I could not verify the 2026-10-22 date from the page. Wider web search found no other source naming Desrosiers.
- No public repo, slide deck, notebook, blog or YouTube video for this workshop turned up in WebSearch. Searches for a Nimble YouTube workshop found only docs and cookbooks. I did not browse YouTube directly, so a video may exist.
- Closest public material:
  - Cookbook index (about 45 app recipes): https://github.com/Nimbleway/cookbook
  - Quickstart walkthrough (competitive shoe analysis across Amazon, Walmart, Nike from one prompt): https://docs.nimbleway.com/nimble-sdk/getting-started/quickstart
  - Skills overview: https://docs.nimbleway.com/integrations/agent-skills/web-search-skills/overview
  - Fresh repo with a MongoDB Atlas Agent Engine starter, updated 2026-10-15 (probably event-adjacent, inferred): https://github.com/Nimbleway/nimble-agent-engine-starter
  - Claude Managed Agents recipe using Nimble MCP: `cookbook/claude-managed-agents/README.md`

## 9. Takeaways for the "cut bloat before the LLM" question

- Nimble does not do heavy server-side compression of web content that I could verify. The levers are choice of mode (lite vs rich), markdown vs HTML, typed schemas (templates, `output_schema`, parser), and a JSON-path filter on the client (`--transform`).
- The honest summary from their own docs: for token efficiency, use the CLI plus files plus slicing rather than the MCP, since MCP pushes results through the context window.
- Biggest unknowns: MCP server internals (closed), whether `fast` depth exists in the live API, and what the 51% figure actually measures.

## Sources

- https://luma.com/oct10lab
- https://github.com/Nimbleway/agent-skills
- https://github.com/Nimbleway/cookbook
- https://github.com/Nimbleway/nimble-cli
- https://github.com/Nimbleway/Public-benchmarks
- https://docs.nimbleway.com
- https://docs.nimbleway.com/integrations/mcp-server/mcp-server.md
- https://docs.nimbleway.com/nimble-sdk/web-tools/search.md
- https://docs.nimbleway.com/nimble-sdk/admin/pricing.md
- https://www.nimbleway.com/pricing
- https://siliconangle.com/?p=798244
- https://siliconangle.com/2026/07/29/nimble-launches-web-search-agents-cut-ai-research-token-costs/
- https://letsdatascience.com/news/nimble-launches-domain-aware-web-search-agents-63611420
- https://venturebeat.com/orchestration/nimble-claims-its-new-domain-specialized-web-search-agents-cut-token-costs-in-half-while-boosting-retrieval-accuracy
