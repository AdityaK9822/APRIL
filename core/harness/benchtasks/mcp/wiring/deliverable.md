# Deliverable notes — mcp-wiring.json

Forced path: `deliverables/mcp-wiring.json` (workspace-relative). Valid JSON.

Content shape:

- Top-level key `servers`: an entry per catalog server with at least `id`,
  `transport`, `command_or_url` (verbatim from the catalog), `tools`,
  `boundaries` (as the catalog states, or `unknown`), `failure_behavior`, `notes`.
- Top-level key `out_of_scope`: what was deliberately left unwired.

Transport facts are quoted from the catalog, never invented: stdio servers
start from the catalog command per session; HTTP servers are reached at the
catalog URL within the auth scope the catalog gives.
