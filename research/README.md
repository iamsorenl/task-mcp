# task-mcp-research

Started 2026-10-26. The question: can I build an MCP creator that takes a bloated API and serves the LLM only what a task needs, to save tokens?

Inspired by Nexla's "How We Built Agents That Build Task-Specific MCP Servers" talk (Abhijit Bharadwaj, Production Agent Lab, 2026-10-22, 1590 Bryant St SF). Nimble also ran a workshop there.

## Files
- `01-nexla.md`: MCP Studio, how it builds servers, its benchmarks
- `02-nimble.md`: Nimble's agent tools and how they keep output small
- `03-prior-art.md`: generators, trimming proxies, Code Mode, papers, gaps
- `04-measurement-and-apis.md`: how to measure savings, plus 16 test API calls with sizes
- `../samples/`: raw JSON responses pulled 2026-10-26
- `../scripts/stat.py`, `../scripts/trim.py`: size and key counting, trim demo

## Takeaways (checked by hand)
1. Nexla's wins come mostly from **fewer turns**: account and date window are fixed when the server is built, and there are fewer, task-shaped tools. Trimming fields is only a small part of it. In Google Ads it took 1 tool call per task vs 4.7 for the native server.
2. **Token savings != cost savings.** arXiv 2607.12161: a 38% cut in tool-output tokens raised billed cost 6.8%, because prompt caching dominates the bill and the agent took extra turns.
3. **Raw responses really are bloated.** PokeAPI pikachu is 309 KB (about 92k tokens), and a typical task needs about 41 tokens of it.
4. **Gap nobody fills:** learn which fields get used from real agent traces, generate a task-specific server, and judge it on cost per solved task, with a `fields` fallback for when the trim misses something.

## Open questions before building
- Target: task-specific server generator (Nexla-style) or a trimming proxy in front of any MCP server?
- Measure in billed cost (with caching), not just tokens?
- How does this fit with mcp-compat (same harness and local models)?
