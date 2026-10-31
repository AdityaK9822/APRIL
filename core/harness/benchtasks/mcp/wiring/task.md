# MCP wiring — bind three servers into the workspace agent

You are staging MCP integrations for this workspace from a catalog snapshot.
The authoritative source is `input/mcp_catalog.json` — every fact about a server
(id, transport, command or URL, tools it exposes, risk band) comes from that
file. Nothing is started here: servers in the snapshot are reachable, not live,
and this run's product is the wiring document.

For each of the three catalog servers:

1. Bind `transport` exactly as the catalog declares it (a stdio server starts
   from the catalog command per session; an HTTP server is reached at the
   catalog URL within its auth scope). Do not improve, rename or substitute a
   transport the catalog does not declare.
2. List the tools you would enable for THIS workspace, only from the catalog's
   tool list, and say why the workspace needs each one.
3. State the authority boundary as the catalog's `scope` / `allow` fields give
   it — where the catalog is silent, write `unknown` and say what a human must
   confirm before first use. A tool being reachable is not a tool permitted.
4. State the failure behavior: what a stalled or rejected call looks like for
   that transport and what the workspace proceeds with while it is down.

## Deliverable

Write the deliverable to `deliverables/mcp-wiring.json` in the workspace. The
file must exist, be valid JSON, and have an entry per server (keyed `servers`)
with at least: `id`, `transport`, `command_or_url` (verbatim from the catalog),
`tools` (your enabled subset), `boundaries` (as the catalog states or `unknown`),
`failure_behavior`, and `notes`. One extra top-level key `out_of_scope` lists
anything you deliberately left unwired.
