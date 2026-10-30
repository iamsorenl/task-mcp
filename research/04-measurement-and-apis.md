# 04 - Measurement and test APIs for a response-trimming MCP generator

Date: 2026-10-26. Everything marked (MEASURED) was curled/computed today in this session. Everything marked (EST) is an estimate. Everything marked (CLAIM) is a number from someone else's page that I did not reproduce.

Token counts below use tiktoken `o200k_base` (OpenAI tokenizer) on compact-or-raw JSON bytes as returned. Claude's tokenizer is different: Anthropic says Claude 4.7+ and later models count ~30% more tokens for the same text than earlier models (https://platform.claude.com/docs/en/build-with-claude/token-counting). So treat o200k counts as a relative yardstick (ratios hold, absolutes drift) and recount with `count_tokens` against the exact target model before quoting numbers.

---

## 1. Measurement

### 1.1 Counting tokens

- Anthropic `POST /v1/messages/count_tokens`: free, accepts the same body as Messages (system, tools, messages, images, PDFs). Rate limits 5,000/10,000/20,000 RPM by tier. The count is an estimate (small deviations from billed). It does NOT work with server tools or the MCP connector (returns invalid_request_error), and does not model prompt caching. It counts under the tokenizer of the `model` you pass, so count against the model you test. Source: https://platform.claude.com/docs/en/build-with-claude/token-counting
- For real runs, do not rely on count_tokens. Read `usage` from each Messages response (input_tokens, output_tokens, cache_read/creation tokens) and sum across the whole agent loop. That is the billed truth, and it captures the effect that matters: a big tool result gets re-sent as input on every later turn.
- tiktoken for OpenAI-family models (`o200k_base` for GPT-4o/5-class). Use it for offline, fast, no-key counting of raw API payloads (what I did below). Good for ranking APIs and sizing trims; not for Claude billing claims.
- Count three buckets separately: (a) tool-definition tokens (schemas/descriptions injected every turn), (b) tool-result tokens, (c) model output tokens. Your tool trims (b); a generator that also shrinks (a) should report it separately. Speakeasy's dynamic-toolset numbers are mostly (a): 100-tool static set 159,218 tokens vs 8,401 dynamic on a simple task (CLAIM, vendor): https://www.speakeasy.com/docs/mcp/build/toolsets/dynamic-toolsets

### 1.2 A/B design that is credible

Recommended (my design, EST of what is sufficient, not a published standard):

1. Same task set, same model, same agent loop, same system prompt, temperature as low as the model allows. Only the tool-result layer differs: ARM A = raw API passthrough MCP server; ARM B = trimmed MCP server. Optional ARM C = hand-written expert projection (an upper bound for "what a careful human would trim").
2. Tasks need machine-checkable ground truth. MCPMark does this by running a verification script against final environment state after resetting to a known initial state, with no LLM judge (https://arxiv.org/html/2509.24002v1). For read-only public APIs, use questions with exact-match or numeric answers ("which of the 5 newest open react issues has label X", "highest temperature in the next 12 hours"), computed from the raw payload by code.
3. Record fixtures. Live APIs drift (NWS, HN, GitHub change hourly). Run both arms against recorded responses (a replay proxy) so the only variable is the trim. Use live runs as a secondary check.
4. Repeat each task k times per arm (MCPMark uses 4 runs and reports pass@1 as mean +/- std, pass@4, and pass^4 = all four succeed). Use pass^k as your "did the trim make it flaky" metric: MCPMark found top models' pass^4 far below pass@1 (gpt-5-medium 52.56 vs 33.86), so single runs hide instability. Paired comparison per task (McNemar or bootstrap on per-task deltas) beats comparing two aggregate percentages.
5. Report the cost frontier, not one number: tokens saved vs success delta, per task and in aggregate, with confidence intervals. Report success-conditional token savings too (tokens on tasks both arms solved) so failures that end early do not look like savings.

### 1.3 Metrics that matter

| Metric | Why | Notes |
|---|---|---|
| Task success rate (verifier-checked) | The guardrail. Savings only count if this does not drop | Primary; pass@1 and pass^k |
| Total input tokens per task, summed over all turns (from `usage`) | The thing you are selling | Also split cached vs uncached; caching changes dollar cost, not raw count |
| Tool-result tokens per call and per task | Isolates your layer | Compute from logged results |
| Number of turns / tool calls per task | A bad trim causes re-fetches and extra calls that eat the savings | MCPMark: 16.2 turns, 17.4 tool calls avg per task (CLAIM, abstract of https://arxiv.org/pdf/2509.24002). MCP-Bench Table 6 gives rounds and calls per model (e.g. gpt-5 9.2 rounds, 78.9 calls) (https://arxiv.org/html/2508.20453) |
| Re-fetch / second-call rate on the same resource | Direct detector of "trim dropped something" | See 1.5 |
| Latency (wall clock, p50/p95) | Trimming adds server-side work; LLM-based pruning adds a model call | Anthropic's tool-writing guide tracks runtime of individual calls and whole tasks (https://www.anthropic.com/engineering/writing-tools-for-agents) |
| Cost in USD | Aggregates in/out/cached pricing | MCPMark reports per-task USD: gpt-5-medium 1.00, claude-sonnet-4 1.99, claude-opus-4.1 9.18, and says cost is not a proxy for performance (https://arxiv.org/html/2509.24002v1) |
| Tool errors | Bad parameter errors can come from trimmed field names | Anthropic suggests tracking tool errors with accuracy, runtime, calls, tokens |

Anthropic's own recommended eval loop for tools: dozens of realistic multi-call tasks with verifiable outcomes, one simple agent loop, and tracking accuracy, runtime, total tool calls, total tokens, and errors. Their example: a "concise" response format used 72 tokens vs 206 for "detailed" (about a third), but concise omitted IDs that later calls need. That is the exact risk you are building around. Same source as above. Claude Code caps tool responses at 25,000 tokens by default.

### 1.4 How the existing MCP benchmarks report (and what they omit)

| Benchmark | Scale | How scored | Reported efficiency | Token reporting |
|---|---|---|---|---|
| MCP-Bench (Accenture/Berkeley) https://arxiv.org/html/2508.20453 | 28 live MCP servers, 250 tools | Rule-based from traces (valid tool name rate, schema compliance, execution success) plus LLM judge (o4-mini, 1-10 on task completion, tool usage, planning, prompts shuffled 5x and averaged) -> overall score; top gpt-5 0.749, o3 0.715 | Avg rounds and tool calls per model (Table 6) | None reported (per the fetch) |
| MCPMark (NUS) https://arxiv.org/html/2509.24002v1 | 127 tasks; Notion, GitHub, Filesystem, Playwright, Postgres | Programmatic verification of end state, env reset; pass@1 (mean of 4 runs), pass@4, pass^4; 100-turn cap | Avg turns, tool calls, USD cost per task; input/output tokens in appendix | Yes, appendix (I could not read the columns cleanly) |
| MCP-Universe (Salesforce) https://arxiv.org/abs/2508.14704 | 6 domains, 11 real MCP servers, ~231 tasks (alphaxiv listing) | Execution-based evaluators: format, static, dynamic (live ground truth for time-varying answers). GPT-5 43.72% (abstract of arXiv version I fetched; the NeurIPS page says 44.16%, so versions differ) | Steps | Abstract says input tokens grow rapidly with interaction steps; calls long context a main difficulty. That is your thesis, cite it |
| LiveMCPBench https://arxiv.org/html/2508.01780v1 | 95 tasks, 70 servers, 527 tools | LLM judge (LiveMCPEval, DeepSeek-V3) with ~81% agreement to humans (text also says 78.95%, internally inconsistent); Claude-Sonnet-4 78.95% success | Steps and tool counts (Sonnet-4 20.09 steps) | No tokens; cost only as a log-price plot |

Takeaways for your design: (1) none of them isolates response size as a variable, so there is no off-the-shelf "trim vs not" number to compare against; you have to build the A/B. (2) The two with deterministic or execution-based scoring (MCPMark, MCP-Universe) are the better template for a trim study than the LLM-judge ones, because an LLM judge can be fooled by fluent answers built on missing data. (3) Their task servers (GitHub, Notion, Postgres, Salesforce) are exactly the bloat candidates, so you could rerun a subset of their tasks with your trimmed servers; check each repo's license/setup first (not verified here).

### 1.5 The "trim removed a field the model needed" risk, and how people detect it

Published approaches (what exists):
- ACON (Microsoft/KAIST, arXiv 2510.00615, https://arxiv.org/abs/2510.00615v2): compresses observations and histories; improves its compression guideline by finding cases where the uncompressed context succeeds but the compressed one fails, then revising the guideline from failure analysis. Reported 26-54% peak-token reduction while largely preserving accuracy; >95% accuracy kept when distilled into a smaller compressor (CLAIM from search summary; check tables before quoting). This "full passes, compressed fails" paired-diff loop is the single most reusable detection idea.
- Squeez (arXiv 2604.04979, https://arxiv.org/abs/2604.04979): fine-tuned Qwen 3.5 2B that returns the minimal verbatim evidence block for a task; recall 0.86, F1 0.80 at 92% input-token removal on a 618-example curated test set. It evaluates pruning with recall of needed evidence, which is a direct metric for "did we keep the needed part."
- SWE-Pruner Pro (arXiv 2607.18213): line-level pruning using the agent's own hidden states, up to 39% token saving (CLAIM via a secondary summary only; not verified).
- Anthropic tool-writing guide: look at transcripts; redundant calls signal truncation/pagination trouble, invalid-parameter errors signal unclear descriptions.

My recommended detectors (design, not published prior art):
1. Paired-failure mining: run ARM A and ARM B; every task where A passes and B fails is a candidate dropped-field case. Diff the tool results, find which trimmed field the A transcript actually cited.
2. Field-citation check on ARM A (the raw run): log which JSON paths' values appear in the model's reasoning, later tool arguments, or final answer. Any path your trim would drop that is cited = a measured miss. Doubles as training data for approach 3.3 below.
3. Needed-field oracle per task: for answerable-by-code tasks, record the minimal set of paths needed to compute the ground truth; check trim output is a superset (recall of needed paths, like Squeez). Cheap and deterministic.
4. Behavioral tell: after a trim, watch for re-fetch of the same resource, a call asking for a field name that was trimmed, "I don't have that information" answers, and hallucinated values (answers correct only by luck). Alert on rate changes between arms.
5. Identifier safety: always keep IDs, cursors, and links that later calls need (Anthropic's concise example drops IDs). A separate unit test: every parameter of every other tool in the server must be satisfiable from trimmed output.
6. Adversarial/"canary" tasks: deliberately ask about rarely-used fields (e.g. a label color, a milestone due date) to see whether the trim is over-fitted to the common tasks.

---

## 2. Candidate test APIs

### 2.1 Measured today (free, no key) - MEASURED

Tokens are o200k on the raw body. "keys" = total dict key occurrences including repeated array elements; "top" = top-level keys of the object (or of first element for lists). "Task trim" = my hand-written projection for an illustrative task, re-tokenized (shows the achievable ceiling, not what a tool would safely do for all tasks).

| # | API / call | Bytes | Tokens | Top-level keys | Total key occurrences / depth | Fields a typical task uses | Task trim tokens |
|---|---|---|---|---|---|---|---|
| 1 | PokeAPI `GET /api/v2/pokemon/pikachu` https://pokeapi.co/api/v2/pokemon/pikachu | 309,106 | 92,539 | 21 | 10,239 / depth 7 | name, types, base stats (or one ability) | 41 (name, types, 6 stats) |
| 2 | PokeAPI `/pokemon-species/pikachu` | 50,860 | 14,923 | 27 | 1,326 / 4 | flavor text in one language, egg groups, evolution chain URL | not measured (mostly multilingual duplicates) |
| 3 | SEC EDGAR `data.sec.gov/submissions/CIK0000320193.json` (Apple; needs only a User-Agent) https://www.sec.gov/search-filings/edgar-application-programming-interfaces | 163,917 | 76,594 | 24 | 77 / 4 (but 16,086 leaf values: columnar arrays, 1,002 filings x 16 columns) | last N filings: form, date, accession no. | 293 (last 10, 3 fields) |
| 4 | NWS hourly forecast `api.weather.gov/gridpoints/MTR/85,105/forecast/hourly` https://www.weather.gov/documentation/services-web-api | 162,386 | 37,497 raw (26,158 compact) | 4 | 3,452 / 5 (156 periods) | next 12 h: time, temp, shortForecast | 354 |
| 5 | CoinGecko `/api/v3/coins/bitcoin` https://docs.coingecko.com/ | 107,434 | 40,247 raw (47,546 compact) | 34 | 4,402 / 4 | current USD price, 24h change | 20 |
| 6 | GitHub REST `GET /repos/facebook/react/pulls?per_page=5` https://docs.github.com/en/rest | 92,512 | 24,832 | list of 5, 36 keys per PR | 1,708 / 5 | number, title, author, draft, created_at | 266 |
| 7 | NWS active alerts `/alerts/active?area=CA` (9 alerts at fetch time) | 48,644 | 13,355 raw (11,346 compact) | 5 | 490 / 6 | event, severity, areaDesc, expires | 427 |
| 8 | Hacker News Algolia `/api/v1/items/8863` (full comment tree) https://hn.algolia.com/api | 41,342 | 11,292 | 13 | 936 / depth 11 | top-level comment text, authors | not measured |
| 9 | TVmaze `/shows/1?embed=episodes` https://www.tvmaze.com/api | 33,698 | 9,682 | 24 | 903 / 6 (39 episodes embedded) | name, status, episode titles | not measured |
| 10 | GitHub REST `GET /repos/facebook/react/issues?per_page=5` | 28,665 | 7,987 | list of 5, 33 keys per issue | 395 / 4 | number, title, state, user, labels, created_at | 300 |
| 11 | Art Institute of Chicago `/api/v1/artworks?limit=5` https://api.artic.edu/docs/ | 24,423 | 7,615 | 4 | 620 / 7 | title, artist, date | not measured |
| 12 | Rick and Morty `/api/character?page=1` | 19,496 | 5,898 | 2 | 326 / 4 | name, status, species | not measured |
| 13 | HN Algolia `/search?query=mcp&hitsPerPage=10` | 13,466 | 4,889 | 13 | 289 / 6 | title, url, points, num_comments, objectID | 499 |
| 14 | NWS 7-day forecast `/gridpoints/MTR/85,105/forecast` | 13,085 | 3,225 raw (2,404 compact) | 4 | 244 / 5 (14 periods) | name, temp, shortForecast | 294 |
| 15 | Open-Meteo `/v1/forecast?...&hourly=temperature_2m,precipitation` (already projected via query params) | 5,179 | 3,285 | 9 | 15 / 3 (514 leaf numbers) | all of it | n/a - control case: bytes are real data, no bloat |
| 16 | GitHub REST `GET /repos/facebook/react` | 5,952 | 1,502 | 86 | 129 / 2 | stars, forks, open_issues, default_branch, pushed_at | not measured (a few dozen tokens) |

Notes on the numbers:
- Ratios: trims for #1, #5, #6, #10, #3 cut well over 95% of tokens. Do not generalize: those projections answer one narrow question. Report trimmed size per task, not per API.
- GitHub lists carry embedded `user`/`repo`/`head`/`base` objects, 36 `*_url` fields per object, etc. (MEASURED key counts above). That template-URL noise is the cleanest example of tokens with no task value.
- Open-Meteo is a good control: the caller already chose fields, so a trim tool should save ~0 here. If your tool "saves" tokens there, it is dropping real data.
- NWS raw tokens exceed compact tokens because of whitespace/indentation in the pretty-printed response; always tokenize what the model will actually see.
- GitHub unauthenticated rate limit is 60 requests/hour per IP, per the docs (https://docs.github.com/en/rest/using-the-rest-api/rate-limits-for-the-rest-api); for repeated A/B runs use a token or recorded fixtures. NWS asked for a User-Agent; I sent a custom one. Two calls failed: restcountries v3.1 now returns "API version deprecated" (v5 migration) and SpaceX API v5 returned a 522 error today, so skip both. Reddit's JSON endpoint returned an HTML page to curl, so skip it.

### 2.2 The named candidates not measured (need key or account) - all EST, no numbers invented

I did not call these. Characterizations come from docs, not my measurement.

| API | Access | Why it's a candidate | Fields typically used | Size claim |
|---|---|---|---|---|
| Stripe (test mode) | Free test key; Stripe has `expand` to inline related objects, which grows payload; nested expansion max depth 4 (https://docs.stripe.com/api/expanding_objects, https://stripe.dev/blog/doing-more-with-less-reducing-requests-to-the-stripe-api). No sparse-field parameter found | Customers/charges/invoices are wide objects with many nullable fields | id, amount, currency, status, customer, created | EST: unmeasured; create a test charge and measure |
| Jira Cloud | Free tier (10 users) + API token | Issue search returns all navigable fields by default; `fields=summary,status` and `expand=` control it (https://developer.atlassian.com/cloud/jira/platform/rest/v3/intro/). Descriptions/comments are Atlassian Document Format trees, very token-heavy | key, summary, status, assignee, priority | EST: unmeasured; a good "projection already exists but agents don't use it" case |
| Notion | Free workspace + integration token | Page retrieve returns every property with type metadata; no official response filter on that endpoint, only the single-property endpoint (https://developers.notion.com/reference/retrieve-a-page, https://developers.notion.com/reference/page-property-values). MCPMark includes Notion tasks | A few property values | EST: unmeasured |
| Salesforce | Free Developer Edition org | sObject describes and records return many fields; MCP-Universe uses a Salesforce server | A handful of fields via SOQL SELECT | EST: unmeasured |
| HubSpot | Free CRM + private app token | Contact/deal objects have `properties` maps and associations | name, email, stage, amount | EST: unmeasured |
| Shopify | Free dev store | Admin REST orders/products are wide; GraphQL is already projected | order name, total, status, line items | EST: unmeasured |
| Google Maps Places (New) | Needs key + billing account (free monthly credit) | Field mask is REQUIRED for Place Details/Search, and billing is by highest SKU of the fields requested (https://developers.google.com/maps/documentation/places/web-service/preview-billing). So here trimming saves money at the API, not just tokens | name, rating, address, openNow | EST: unmeasured; not a "no auth" API |
| Spotify | Free app; client-credentials token | Track/album/artist objects carry market lists, available_markets arrays (long), image URLs | name, artist, uri | EST: unmeasured; known for `available_markets` arrays, verify |

Recommended starter set of 10, ranked by "free, no key, bloated, tasks easy to verify by code": PokeAPI, SEC EDGAR submissions, NWS (3 endpoints), GitHub issues and PRs (token optional), CoinGecko coin, HN Algolia (item tree), TVmaze embed, Art Institute of Chicago, Open-Meteo (control), plus one keyed enterprise API (Jira or Stripe test mode) to show it is not only toy APIs. Add Open-Meteo as the explicit zero-savings control.

---

## 3. Approaches for deciding what to keep

| Approach | Pros | Cons | Fits this set |
|---|---|---|---|
| A. Static schema rule per task (hand/declarative allowlist or denylist per tool) | Deterministic, zero runtime cost, auditable, trivially testable (recall against needed-path oracle). Matches Anthropic's advice of sensible defaults and concise/detailed modes | Does not scale to hundreds of endpoints; someone must know the task; brittle when tasks change; silent misses | Good baseline and fallback; also the ARM C upper bound |
| B. LLM prunes the schema once at generation time (reads OpenAPI + example responses + intended tasks, emits allowlist per tool) | One-time cost, then runtime is free and deterministic; scales across many endpoints; output is a reviewable artifact; can drop obvious noise (`*_url` templates, `node_id`, multilingual duplicates) | Only sees schema + a few examples, so rare-but-needed fields get cut; no feedback unless you add eval; task intent must be guessed. Needs the paired A/B in 1.5 to be trusted | Best default for the generator product. Pair with approach D (escape hatch) |
| C. Learn from logged agent traces which fields get used | Data-driven; reflects real tasks; field-citation logging from 1.5 gives labels; ACON-style failure mining refines guidelines | Cold start (needs traces); biased toward the traces' tasks (new task = dropped field); attribution of "used" is noisy (model reads a field but does not cite it; cited by paraphrase). Privacy of logged payloads | Strong second phase; use for tightening B's output, and as the A/B detector |
| D. Runtime summarization/extraction by a small model, conditioned on the task | Adapts per request; Squeez shows a fine-tuned 2B model hits recall 0.86 at 92% token removal for verbatim extraction (https://arxiv.org/abs/2604.04979); ACON distills compressors to small models keeping >95% accuracy (CLAIM) | Adds latency and cost per call, another failure surface; abstractive summaries can rewrite or invent numbers (use extraction, not paraphrase); needs the task text passed to the tool; nondeterministic; breaks caching and reproducibility | Use for unstructured/long bodies (comments, descriptions), not for field-level JSON |
| E. Let the model request fields (projection params: `fields=`, GraphQL-style, Google field masks, Jira `fields`, Anthropic concise/detailed `response_format`) | Zero information loss by construction for requested fields; model decides per task; many APIs already support it (Jira, Google Places field masks, GitHub GraphQL) | Costs tokens in the tool schema (field enum lists can be large) and relies on the model knowing field names; models over-request or under-request, and can only ask for what they know exists; an extra round trip if they need to explore; no help on APIs without projection | Complement to B: ship a default trimmed view plus an optional `fields`/`include` escape hatch and a "truncated, N more fields available" hint, so a miss is recoverable instead of silent |

Suggested shape (design recommendation): default view from B (generation-time, reviewable), escape hatch from E (recoverability), refine B with C-style miss mining, use D only for free-text blobs. Measure each addition with the 1.2 A/B; the key quantity for E is the re-fetch rate, which shows the cost of a miss.

---

## Sources
- Anthropic token counting: https://platform.claude.com/docs/en/build-with-claude/token-counting
- Anthropic, writing tools for agents: https://www.anthropic.com/engineering/writing-tools-for-agents
- Anthropic, code execution with MCP (150,000 -> 2,000 tokens, 98.7%, a worked example of filtering results outside the model context; vendor claim): https://www.anthropic.com/engineering/code-execution-with-mcp
- MCP-Bench: https://arxiv.org/abs/2508.20453 (HTML https://arxiv.org/html/2508.20453)
- MCPMark: https://arxiv.org/abs/2509.24002 (HTML https://arxiv.org/html/2509.24002v1)
- MCP-Universe: https://arxiv.org/abs/2508.14704
- LiveMCPBench: https://arxiv.org/abs/2508.01780
- ACON: https://arxiv.org/abs/2510.00615
- Squeez: https://arxiv.org/abs/2604.04979
- SWE-Pruner Pro (unverified, via search summary): https://arxiv.org/pdf/2607.18213
- Speakeasy dynamic toolsets (vendor): https://www.speakeasy.com/docs/mcp/build/toolsets/dynamic-toolsets
- GitHub rate limits: https://docs.github.com/en/rest/using-the-rest-api/rate-limits-for-the-rest-api
- Google Places billing/field masks: https://developers.google.com/maps/documentation/places/web-service/preview-billing
- Stripe expand: https://docs.stripe.com/api/expanding_objects
- Jira REST v3: https://developer.atlassian.com/cloud/jira/platform/rest/v3/intro/
- Notion page API: https://developers.notion.com/reference/retrieve-a-page

Raw fixtures and scripts for the measurements: /private/tmp/claude-503/-Users-Soren/a8119ac8-d7ae-4de2-b680-af5846e3df04/scratchpad/s/ (JSON), .../scratchpad/stat.py and trim.py. Move these into the project if you want them reproducible.
