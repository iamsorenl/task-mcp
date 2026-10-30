# Prior art: OpenAPI-to-MCP generators and MCP response-bloat reduction

Date of survey: 2026-10-26. Stars / last-push from `gh` on that date.
Sources: web search, WebFetch of primary pages, `gh`. "Vendor claim" = number from the project's own page, not independently checked. "(inferred)" = my reading, not stated by a source.

Goal: find what exists for "give it an API, get an MCP server that works out which response fields the LLM needs", and where the gap is.

Addressing response bloat: **Y** = yes, **P** = partial / opt-in / manual, **N** = no or not documented.

---

## 1. Comparison table

| # | Item | Category | What it does | Response bloat? | Open source? | Stars / last push |
|---|------|----------|--------------|-----------------|--------------|-------------------|
| 1 | FastMCP `from_openapi` | Generator | Every endpoint becomes a Tool; RouteMaps, `mcp_names`, `mcp_component_fn` | **N** (docs page silent on response size/fields) | Apache-2.0 | 28,209 / 2026-10-26 |
| 2 | Stainless MCP | Generator (SaaS) | Generated MCP server; per-call `jq_filter` (2025 changelog); current docs describe a TypeScript code-execution tool | **P** (model-written jq / code) | Generator closed (inferred); CLI repo Apache-2.0 | stainless-api-cli 25 / 2026-07-18 |
| 3 | Speakeasy MCP + Gram | Generator + gateway | OpenAPI to MCP, curated toolsets, dynamic toolsets, `x-gram responseFilterType: jq` | **P** (jq opt-in, experimental) | Gram AGPL-3.0; generator licence not verified | gram 275 / 2026-10-26 |
| 4 | openapi-mcp-generator (harsha-iiiv) | Generator | Emits a TS project; `--output-schema` validates responses | **N** (validation, not trimming) | MIT | 640 / 2026-10-24 |
| 5 | mcp4openapi (davidruzicka) | Generator/runtime | Hand-written JSON "profiles": fewer tools, "response field filtering" | **P** (manual config; mechanism undocumented on README) | MIT | 0 / 2026-10-25 |
| 6 | oapi-invoker-mcp (mcpc-tech) | Generator/runtime | `x-response-config`: `maxLength`, `includeResponseKeys`, `excludeResponseKeys`, masking | **P** (static, hand-set) | MIT | 5 / 2026-07-31 |
| 7 | FieldFlow | Wrapper | OpenAPI to FastAPI routes with `fields` param, optional MCP layer | **Y** (field projection) but caller chooses | repo has licence field unread | 110 / 2026-07-22 |
| 8 | mcpopt (MichaelTheMay) | Optimizer | Synthesizes evals, rewrites tool *descriptions* | **N** (descriptions only) | MIT | 1 / 2026-09-08 |
| 9 | Composio | Platform | 1000+ toolkits; Tool Router with remote workbench/bash sandbox for large outputs | **P** (offload to sandbox, no field learning) | MIT (SDK repo) | 30,766 / 2026-10-26 |
| 10 | Zapier MCP | Platform | Hosted MCP over Zapier actions | **N** (no response-size doc found) | Closed | n/a |
| 11 | Apollo MCP Server | GraphQL to MCP | GraphQL operations become tools; GraphQL selects fields | **P** (selection is fixed per operation; no token numbers) | check repo | 317 / 2026-10-26 |
| 12 | Higress openapi-to-mcpserver | Generator | OpenAPI to Higress MCP config | not checked | Apache-2.0 | 291 / 2026-04-17 |
| 13 | Taskade MCP codegen | Generator | OpenAPI to MCP codegen | not checked | MIT | 170 / 2026-10-26 |
| 14 | twilio-labs/mcp | Generator | OpenAPI to MCP tool generator | not checked | MIT | 113 / 2026-02-14 |
| 15 | AutoMCP (arXiv 2507.16044) | Research generator | Spec repair + tool filtering/regrouping | **N** (tool count, not response size) | released with paper | n/a |
| 16 | Cloudflare Code Mode (MCP) | Calling pattern | 2 tools, `search()` and `execute()`, agent writes JS | **P** (mainly definitions; code can trim results) | cloudflare/mcp-server-cloudflare Apache-2.0 | 4,419 / 2026-10-22 |
| 17 | Anthropic code execution with MCP | Calling pattern | Tools as code APIs; filter in sandbox | **Y** for results and definitions | Post only | n/a |
| 18 | Anthropic Tool Search / defer_loading | Calling pattern | Load tool definitions on demand | **N** for results; Y for definitions | API feature | n/a |
| 19 | Speakeasy dynamic toolsets | Calling pattern | search / describe / execute meta-tools | **N** for results; Y for definitions | in Gram (AGPL) | see 3 |
| 20 | mcp-compressor (Atlassian Labs) | Proxy | Compress tool descriptions; opt-in `--shrinkfit` response cap | **P** | Apache-2.0 | 137 / 2026-10-25 |
| 21 | mcp-rtk | Proxy | 8-stage response filter pipeline, hand-written TOML presets | **Y** (static rules) | MIT | 4 / 2026-04-23 |
| 22 | jmunch-mcp | Proxy | Replaces fat payloads with handles + peek/slice/search/aggregate | **Y** | MIT | 33 / 2026-09-01 |
| 23 | tooltrim (nac7) | Library/proxy | Extractive compression, BM25 query-aware, `expand()` ref | **Y** | MIT | 3 / 2026-08-11 |
| 24 | mcp2cli | CLI conversion | MCP/OpenAPI/GraphQL to CLI at runtime | **N** (claims are about schemas) | MIT | 2,424 / 2026-10-12 |
| 25 | Squeez, ACON, SWE-Pruner | Research | Learned / task-conditioned pruning of tool output | **Y** (research) | code for SWE-Pruner public | see section 4 |

---

## 2. Generators in detail

### 2.1 FastMCP `from_openapi`
- URL: https://gofastmcp.com/integrations/openapi ; repo https://github.com/PrefectHQ/fastmcp
- Does: "converts every endpoint in your OpenAPI specification into an MCP Tool" by default. Ordered `RouteMap` objects (method, path regex, tags) assign TOOL / RESOURCE / RESOURCE_TEMPLATE / EXCLUDE; `route_map_fn`, `mcp_names`, `mcp_tags`, and `mcp_component_fn` (mutates a component in place) are the customization hooks.
- Response bloat: **N** on the fetched integration page. It does not discuss response size, field filtering, or output schemas. (A hook like `mcp_component_fn` could be used to wrap tools; that is inferred, not documented.)
- Open source: yes, Apache-2.0. 28,209 stars, pushed 2026-10-26.

### 2.2 Stainless
- URLs: https://www.stainless.com/docs/mcp ; changelog https://www.stainless.com/changelog/mcp-servers-now-support-response-data-filtering-using-jq/
- Changelog (2025-07-14): "an additional `jq_filter` parameter on each tool call"; the model shapes the response with jq against its schema. Enabled for all generated MCP servers.
- Current docs: the server "exposes a tool that accepts TypeScript code" (code mode), run locally in Deno (`--code-execution-mode=local`); Stainless-hosted execution is deprecated. The docs page I fetched does not mention jq, so whether `jq_filter` survives in code mode is **unverified**.
- Response bloat: **P**. The model must write the filter or the code; nothing learns which fields matter.
- Open source: the generator is a commercial service (inferred; not stated). `stainless-api/stainless-api-cli` is Apache-2.0, 25 stars, pushed 2026-07-18.

### 2.3 Speakeasy (standalone generator) and Gram
- URLs: https://www.speakeasy.com/docs/gram/build-mcp/response-filtering ; https://speakeasy.com/mcp/tool-design/response-filtering-jq ; https://www.speakeasy.com/blog/generating-mcp-from-openapi-lessons-from-50-production-servers ; repo https://github.com/speakeasy-api/gram
- Response filtering: `x-gram` extension with `responseFilterType: jq`; "more response filter types will be available in future releases"; one copy of the page is labelled experimental. Example in the jq article: `GET /contacts` returns 100 contacts x 20 fields = 2,000 fields; only the example is given, no benchmark.
- Lessons blog: warns about "unnecessary information included in responses, such as metadata" and recommends simplifying deeply nested JSON, but gives no numbers and no explicit field-filter recommendation. Standalone generator passes raw response data through by default (skips Zod validation unless `validateResponse`), per the Speakeasy docs summary found in search.
- Dynamic toolsets (definition side): see section 4.
- Response bloat: **P**. Gram: AGPL-3.0, 275 stars, pushed 2026-10-26. Standalone generator licence: not verified.

### 2.4 openapi-mcp-generator (harsha-iiiv)
- URL: https://github.com/harsha-iiiv/openapi-mcp-generator
- Emits a full Node project (also a Cloudflare Worker target). Filters operations (`--include-tags`, `--exclude-operations`, `x-mcp`), not response fields. `--output-schema` validates responses; no trimming.
- Response bloat: **N**. MIT, 640 stars, pushed 2026-10-24.

### 2.5 mcp4openapi, oapi-invoker-mcp
- mcp4openapi: https://github.com/davidruzicka/mcp4openapi. JSON "profiles" choose which tools are exposed and "how to aggregate them"; lists "Response field filtering (reduce LLM context)" as a feature, but the README does not show the config syntax. Profiles look hand-authored (inferred). MIT, 0 stars, pushed 2026-10-25.
- oapi-invoker-mcp: https://github.com/mcpc-tech/oapi-invoker-mcp. `x-response-config` with `maxLength` (examples 10000 / 50000), `includeResponseKeys`, `excludeResponseKeys` (dot paths, `*`, `**`), `sensitiveResponseFields` masking. This is the closest "config-driven projection per OpenAPI operation" found; all rules are written by a human. MIT, 5 stars, pushed 2026-07-31.

### 2.6 FieldFlow
- URL: https://github.com/guillaumegay13/fieldflow. Generates FastAPI routes that take an optional `fields` list (nested selectors like `types[].type.name`); optional MCP layer over stdio. Measured example: listing 26 open PRs went about 23,722 to 2,779 tokens (88%), but that number is from the separate `fieldflow-cli`, not the HTTP/MCP layer, and is a single example. 110 stars, pushed 2026-07-22. Licence not checked.

### 2.7 mcpopt
- I could not find an "mcpopt" that matches the brief beyond https://github.com/MichaelTheMay/mcpopt ("Synthesize verifier-gated tool-use evals for any MCP server and auto-optimize tool descriptions"). It rewrites tool *descriptions* against a held-out eval gate; the README says nothing about responses. **N** for response bloat. MIT, 1 star, pushed 2026-09-08. If the engineer meant a different "mcpopt", I did not find it.
- Relevant design idea (inferred): the "verifier-gated, held-out-eval" loop is the right shape for validating a field-pruning step too.

### 2.8 Composio
- URLs: https://docs.composio.dev/tool-router/overview ; https://docs.composio.dev/kb/guide/platform-tool-router-workbench ; repo https://github.com/ComposioHQ/composio
- Tool Router exposes meta tools plus a persistent Python workbench (`COMPOSIO_REMOTE_WORKBENCH`) and bash tool so large tool outputs are processed in a sandbox instead of in context. Docs do not state the offload threshold or storage details.
- Response bloat: **P** (offload to sandbox; agent writes the code). MIT, 30,766 stars, pushed 2026-10-26.

### 2.8b Zapier MCP
- URL: https://docs.zapier.com/mcp/usage. Searches found usage/billing docs and no response-size or field-selection documentation. **N** (not documented). Closed source.

### 2.9 Others (not examined for response handling)
- Higress openapi-to-mcpserver https://github.com/higress-group/openapi-to-mcpserver (291, 2026-04-17, Apache-2.0)
- Taskade https://github.com/taskade/mcp (170, 2026-10-26, MIT)
- twilio-labs/mcp https://github.com/twilio-labs/mcp (113, 2026-02-14, MIT)
- automation-ai-labs/mcp-link https://github.com/automation-ai-labs/mcp-link (625, 2025-04-03, MIT)
- tadata-org/fastapi_mcp https://github.com/tadata-org/fastapi_mcp (12,023, last push 2025-11-24, MIT)
- open-webui/mcpo (MCP to OpenAPI, reverse direction) https://github.com/open-webui/mcpo (4,412)
- kadykov/mcp-openapi-schema-explorer https://github.com/kadykov/mcp-openapi-schema-explorer (76, 2026-10-24): token-efficient access to the *spec*, not responses.
- Apollo MCP Server https://github.com/apollographql/apollo-mcp-server (317, 2026-10-26). Docs say precise GraphQL requests reduce "token usage" vs orchestrating REST endpoints; no figures. Field selection is fixed by whoever writes the operation (inferred).

### 2.10 Research: AutoMCP / REST-to-MCP
- arXiv 2507.16044, Mastouri et al., "From REST to MCP". 116 official servers; 92% are bare API wrappers; servers expose a median 19% of API operations; automated generation from 80 OpenAPI contracts succeeds for 76% of sampled tools, 94.2% after spec repair; filtering/regrouping cut median tool count per API by one third. Tool-count focus; nothing on response size. https://arxiv.org/abs/2507.16044

---

## 3. Response-shaping techniques (taxonomy with who does it)

| Technique | Who decides | Examples found | Notes |
|-----------|-------------|----------------|-------|
| Field projection / sparse fieldsets (static) | Human, at config time | oapi-invoker-mcp `include/excludeResponseKeys`; mcp-rtk `keep_fields`/`strip_fields`; mcp4openapi profiles | Cheap, deterministic, but someone must know which fields matter |
| Field projection (per call) | The LLM | FieldFlow `fields` param | Model must know the schema; adds argument tokens |
| jq / JMESPath exposed to model | The LLM | Stainless `jq_filter`; Speakeasy/Gram `responseFilterType: jq`; mcp-jq repos | Model writes the filter blind unless it has seen a sample. Failure mode: bad filter, retry (inferred) |
| GraphQL-style selection | Operation author or LLM | Apollo MCP Server | Needs a GraphQL backend; REST needs a shim |
| Code in sandbox | The LLM | Cloudflare Code Mode, Anthropic post, Composio workbench, Stainless code tool | Most general; costs a sandbox and security surface |
| Generic compression (drop nulls, truncate strings, collapse arrays) | Heuristic | mcp-rtk defaults ("typically saves 30-40%", vendor claim) | No task awareness |
| Query-aware extractive compression | Heuristic scorer | tooltrim (BM25, optional embeddings) | Needs a query string; 7-8B pilot caveats |
| Summarize with small model | Model | tooltrim `LLMDistiller` (optional); jmunch `summarize` in gateway mode; ACON compressor | Adds latency and a call |
| Pagination / truncation | Server or client | Claude Code caps MCP output at 25,000 tokens by default and warns at 10,000 (`MAX_MCP_OUTPUT_TOKENS`); mcp-compressor `--shrinkfit` (20,000 chars) | Blunt; loses the tail |
| Handles / references | Proxy | jmunch-mcp (SQLite for tabular, JSON-tree backend, verbs peek/slice/search/aggregate/describe/list_handles); tooltrim `expand()`; MCP `resource_link` in the spec | Lossless, but adds round trips |
| Store outside context | Agent in sandbox | Composio workbench; Anthropic post (write intermediate results to files) | |

Spec note: MCP 2025-06-18 has optional `outputSchema` and `structuredContent`, and `resource_link` results; `outputSchema` is for validation, and the spec text I read says nothing about limiting or selecting fields. https://modelcontextprotocol.io/specification/2025-06-18/server/tools

Selected proxies' own numbers (vendor claims):
- jmunch-mcp: GitHub (react repo) suite 379,878 to 44,328 tokens (88.3%); Firecrawl suite 259,574 to 2,928 (98.9%). https://github.com/jgravelle/jmunch-mcp
- tooltrim: 5 outputs, 400-token budget, 39,575 to 1,111 tokens (97.2%), planted fact kept 5/5; faithfulness on 62 cases with 7-8B models (mistral:7b 13% full vs 84% at 128-token budget). Its README says the lexical judge and small models mean a frontier model would likely show less uplift. https://github.com/nac7/tooltrim
- mcp-rtk: "60-90%" project claim; no learning, presets hand-written and community-maintained; `discover` estimates savings from session logs but does not generate rules. https://github.com/ThomasTartrau/mcp-rtk

---

## 4. Changing how tools are called (definitions vs results)

| Approach | Tokens on tool definitions | Tokens on tool results | Numbers | URL |
|----------|---------------------------|------------------------|---------|-----|
| Cloudflare Code Mode (MCP) | Large cut: 2 tools (`search`, `execute`), about 1,000 tokens | Indirect: code "can return just the data it needs"; no result-size figures | Cloudflare API >2,500 endpoints; 99.9% input reduction; equivalent MCP would be 1.17M tokens (intro page also says over 2M, unreconciled) | https://blog.cloudflare.com/code-mode-mcp/ |
| Anthropic, code execution with MCP | Large cut: agent reads only the tool files it needs | Large cut: filter in sandbox; 10,000-row sheet, model "sees five rows instead of 10,000"; avoids ~50,000 extra tokens for a 2-hour transcript passing through twice | 150,000 to 2,000 tokens (98.7%) on one Drive-to-Salesforce workflow | https://www.anthropic.com/engineering/code-execution-with-mcp |
| Anthropic Tool Search / defer_loading | Large cut | None | 58 tools about 55K tokens down to about 8.7K (85%); MCP eval accuracy Opus 4 49% to 74%, Opus 4.5 79.5% to 88.1% (via secondary summaries of Anthropic's post) | https://www.anthropic.com/engineering/advanced-tool-use |
| Anthropic Programmatic Tool Calling | n/a | Yes: results processed in code | About 37% token reduction (secondary sources; not confirmed on Anthropic's page by me) | same |
| Speakeasy dynamic toolsets | Large cut | None | Input tokens down 96% (simple) / 91% (complex); total down 96% / 90%; 2-3x more tool calls (docs); "input schemas are 60-80% of tokens in static toolsets" (docs). Vendor numbers | https://www.speakeasy.com/docs/mcp/build/toolsets/dynamic-toolsets |
| Atlassian mcp-compressor | Large cut (descriptions/schemas behind wrapper tools) | Only if `--shrinkfit` | No per-level numbers on README | https://github.com/atlassian-labs/mcp-compressor |
| mcp2cli | Cut (schemas), claimed 96-99% (project claim via search snippet) | not addressed | | https://github.com/knowsuchagency/mcp2cli |
| ToolHive MCP Optimizer | Cut (tool selection) | none | experimental per docs | https://docs.stacklok.com/toolhive/guides-mcp/meta-mcp |

Takeaway (inferred): the big public wins are on the definition side (one-time cost per session, 85-99%). Result-side savings come either from sandbox code (Anthropic, Cloudflare, Composio) or from proxies, and the only per-task-aware mechanisms are model-written filters.

Related repos: Bifrost (https://github.com/maximhq/bifrost, 9,122 stars, Apache-2.0) lists "MCP Code Mode" but its README makes no token or result claims. mcp-tool-search proxies and code-mode wrappers exist at low star counts (e.g. KGT24k/mcp-tool-search 7 stars; acoyfellow/mcp-code-mode; Edison-Watch/mcp-code-mode).

---

## 5. Papers and benchmarks

| Paper | Finding | URL |
|-------|---------|-----|
| Weinberger & Hozez, "Token Reduction Is Not Cost Reduction" (arXiv 2607.12161, Jul 2026) | 2,908 paired Claude Code runs. Most aggressive arm cut delivered tool-output tokens 38.4% yet billed cost rose 6.8%. Pearson r = 0.15 between token reduction and cost reduction. Cache creation+reads about 87% of cost. Aggressive compression lowered patch success on a SWE-bench Go subset and added retrieval/diagnosis turns. **Key warning for this project** | https://arxiv.org/abs/2607.12161 |
| Kovács, "Squeez: Task-Conditioned Tool-Output Pruning for Coding Agents" (2604.04979) | Qwen 3.5 2B + LoRA; 11,477 training examples, 618 test; 0.86 recall, 0.80 F1 while removing 92% of input tokens; beats zero-shot 35B-A3B by 11 recall points | https://arxiv.org/abs/2604.04979 |
| Kang et al., "ACON" (2510.00615, ICML 2026 submission) | Compresses observations and history; guidelines refined from failure analysis in natural language, no fine-tuning; peak tokens down 26-54%; AppWorld, OfficeBench, multi-objective QA. Extra compressor call adds latency | https://arxiv.org/abs/2510.00615 |
| Lindenbauer et al., "The Complexity Trap" (2508.21433, JetBrains/TUM) | Simple observation masking about halves cost and matches LLM summarization on SWE-bench Verified; hybrid cuts a further 7-11% | https://arxiv.org/abs/2508.21433 |
| SWE-Pruner (2601.16746) and Pro (2607.18213) | 0.6B "skimmer" selecting relevant lines given a goal; Pro reports pruning can raise API-call counts | https://arxiv.org/html/2601.16746v1 |
| Felendler et al., "From Tool Orchestration to Code Execution" (2602.15945) | Code-execution MCP "significantly reduces token usage and latency" on MCP-Bench, 10 servers, but expands attack surface (16 attack classes); abstract gives no numbers | https://arxiv.org/abs/2602.15945 |
| Kutschka & Geiger, "Notation Matters" (2605.29676) | TOON/TRON instead of JSON: TRON up to 27% fewer tokens, accuracy within 14 points; TOON up to 18%, about 9 points. On BFCL, MCPToolBench++, MCP-Universe, StableToolBench | https://arxiv.org/abs/2605.29676 |
| Ding et al., "Network and Systems Performance Characterization of MCP-Enabled LLM Agents" (2511.07426) | Context (prompts, tool defs, history) "dramatically inflates token usage"; abstract has no numbers | https://arxiv.org/abs/2511.07426 |
| MCP-AgentBench (2509.09734) | Per-query token use of 101.7k (Kimi K2), 140.3k (Claude 4 Sonnet), 36.5k (o3-mini, 50% pass) as reported in a search summary; mixes thinking tokens, so not a pure tool-output measure | https://arxiv.org/pdf/2509.09734 |
| Mastouri et al., AutoMCP (2507.16044) | See 2.10 | https://arxiv.org/abs/2507.16044 |

Not independently verified (blog/vendor): StackOne "schema bloat vs response bloat" framing (https://www.stackone.com/blog/mcp-token-optimization/); Scalekit/mindstudio claim that CLI is 10-32x cheaper than MCP; edgar.tools claim that most MCP token benchmarks count only input side. I did not open these.

---

## 6. GitHub repos that trim, compress or filter MCP responses

| Repo | Approach | Stars | Last push | Licence |
|------|----------|-------|-----------|---------|
| atlassian-labs/mcp-compressor | Description compression; opt-in response cap | 137 | 2026-10-25 | Apache-2.0 |
| jgravelle/jmunch-mcp | Handle-ifying proxy | 33 | 2026-09-01 | MIT |
| ThomasTartrau/mcp-rtk | 8-stage filter proxy, TOML presets (also on crates.io) | 4 | 2026-04-23 | MIT |
| nac7/tooltrim | Query-aware extractive compression + expand | 3 | 2026-08-11 | MIT |
| false200/tooltrim | Filters the tool *list* (not responses) | 4 | 2026-10-21 | MIT |
| guillaumegay13/fieldflow | `fields` projection | 110 | 2026-07-22 | not checked |
| mcpc-tech/oapi-invoker-mcp | Static include/exclude keys + maxLength | 5 | 2026-07-31 | MIT |
| claudioemmanuel/squeez | Hook-based token compressor for AI CLI hosts (different project from the Squeez paper; I did not confirm they are related) | 220 | 2026-10-19 | not checked |
| Ayanami1314/swe-pruner | Neural pruning of code context | 320 | 2026-06-30 | not checked |
| 247arjun/mcp-jq | jq as an MCP server | 4 | 2025-07-26 | MIT |
| KGT24k/mcp-tool-search | Lazy tool loading (definitions) | 7 | 2026-09-10 | MIT |
| ousamabenyounes/rtk-mcp | MCP bridge for RTK CLI output compression | 12 | 2026-03-17 | none listed |
| IBM/mcp-context-forge, agentgateway/agentgateway, docker/mcp-gateway, microsoft/mcp-gateway | General gateways (4,699 / 5,660 / 1,616 / 897 stars) | | 2026-10 | Apache-2.0 / Apache-2.0 / MIT / MIT |

I did not verify whether the four gateways have any response-shaping feature; treat as **N / unknown**. Search snippets also mentioned mcp-snapshot-filter (browser snapshots, 40-60% claim) and glama-listed compressors, which I did not open or star-check.

Observation (inferred): response-side proxies are tiny projects (under 40 stars except mcp-compressor and the unrelated squeez). Nothing in this list is a de facto standard.

---

## 7. Gaps

What I searched for and did not find: a tool that (a) reads an OpenAPI spec or endpoint list, (b) observes real agent calls, and (c) emits a server whose per-tool response shape has been learned and checked. Everything below is inferred from absence in the sources above; I did one pass of searching, not an exhaustive one.

1. **Learning which fields matter from real task traces, then baking the result into a generated server.** All found projection mechanisms are hand-written (oapi-invoker-mcp, mcp-rtk presets, mcp4openapi profiles) or model-written at call time (jq_filter, code mode, FieldFlow). The learned approaches (Squeez, ACON, SWE-Pruner) run as a *runtime compressor on a context*, are aimed at coding agents/AppWorld, and are not tied to an API schema or emitted as a server. trace2mcp (https://pypi.org/project/trace2mcp/) compiles a successful trace into a workflow with dependency graph and handler stubs, but its description covers call sequence, not response fields; I could not open its page or find its repo.
2. **Schema-level field usage telemetry.** No tool found counts, per operation and per JSON path, which response fields the model later quoted or used in a follow-up call. This would give a ground truth for "needed" that is cheaper than an LLM judge (design idea, inferred).
3. **Verified lossless-enough pruning with a task-success gate.** Only mcpopt applies a held-out eval gate, and only to descriptions. The "Token Reduction Is Not Cost Reduction" paper shows aggressive output compression can raise cost (+6.8%) and lower success, so pruning needs an eval of cost per solved task, with cache effects. No generator ships that check for response shaping.
4. **Safe fallback when a pruned field turns out to be needed.** Handles and `expand()` exist (jmunch, tooltrim) but are generic; none were found that automatically widen a learned projection after a miss (re-fetch, or an "include extra fields" escape hatch) and feed the miss back into the projection.
5. **Generator-time use of the OpenAPI response schema.** Generators use the spec for input schemas and tool grouping (AutoMCP, FastMCP route maps). Nothing found uses response-schema structure (array-of-objects, huge free-text fields such as PR bodies, base64, HTML) to pick default projections, summaries, or handle-ification at generation time. FieldFlow's own example (savings mostly from PR body text) hints that free-text fields dominate (inferred).
6. **Per-task-family variants of one API.** A server specialized for "triage issues" vs "write release notes" would project different fields from the same endpoint. Nothing found generates task-specific servers; Gram toolsets and mcp4openapi profiles are the nearest, hand-curated.
7. **Benchmarks.** No public benchmark found measures tool-*result* token cost across generated OpenAPI servers (most published figures are definition-side or single examples). The Weinberger/Hozez study is coding-agent-specific.
8. **Response-side vs cache-side accounting.** Because cache read/creation dominates billed cost in the one study measuring it, savings claimed as "tokens removed" should be reported as dollars per successful task. Most vendor numbers above are raw token counts.

### Where the three biggest openings are (ranked)
1. Trace-learned, per-operation field projection emitted as a generated server (gap 1 + 2).
2. A pruning eval harness (cost per solved task, with miss recovery) wrapped around any generator (gaps 3 + 4).
3. Schema-aware default shaping at generation time, before any traces exist (gap 5), as a cold-start for item 1.

### Risks to the idea (from the sources)
- Token savings may not equal cost savings (arXiv 2607.12161).
- The model-written jq/code route (Stainless, Speakeasy, Cloudflare, Anthropic) already covers a lot of the problem and improves as models improve; a learned static projection competes with "just let the model write jq against a sample".
- Pruning from traces overfits to past tasks; a miss path is required.
- Anthropic's code-execution post warns about sandboxing and monitoring costs; Felendler et al. report an expanded attack surface for code-execution MCP.

## 8. Caveats
- Stars and push dates are from `gh` on 2026-10-26. Licence "not checked" means I did not read it.
- Several quoted numbers come from search-result summaries of pages I did not open in full (Anthropic advanced tool use, mcp2cli, MCP-AgentBench, Speakeasy dynamic toolset figures); those are marked "secondary" or "vendor".
- The Cloudflare blog's 1.17M figure and its "over 2 million" intro figure are not reconciled by the post.
- I did not read the Gram, Zapier or Composio source; claims about them come from docs pages only.
