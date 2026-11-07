# APRIL Agent Web UI

Frontend prototype inspired by Claude Desktop.

## Dev

Backend (from repository root):

```bash
.venv/bin/python -m core.api
```

Frontend:

```bash
cd web
npm install
npm run dev
```

Open `http://localhost:5173`. The Vite dev server proxies `/api` and `/healthz` to the FastAPI backend on port 8000.

## Build

```bash
cd web
npm run build
```


## DO NOT DELETE

Phase 2 — Modular feature shells (2–3 weeks)
Clone each ZCode feature as independent frontend modules, not direct ports:
1. Terminal
Clone UI + interaction patterns:
- Session list, tab triggers, composed input fallback, terminal theme, resize/full-view patterns.
APRIL backend needed later:
- A PTY execution service. The web app can start with a mock terminal and later connect via WebSocket.
Note: True embedded terminal behavior depends on desktop/local backend support; browser-only is limited.
2. MCP Configurator
Clone UI + interaction patterns:
- Server list, enable/disable, credentials entry, tool inspection, import/export of config.
APRIL backend needed later:
- MCP server registry and runtime client lifecycle.
Phase strategy: Start with JSON config editing UI + validation; add real MCP execution later.
3. Skills Extractor
Clone UI + interaction patterns:
- Discovery walk, skill list, detail view, import from other AI agents, sync status.
APRIL backend needed later:
- File scanning, skill normalization, storage, and version reporting.
Phase strategy: Start with local scan/import UI using APRIL’s skill directory; later add extractors.
4. Hooks Manager
Clone UI + interaction patterns:
- Hook list, event-type scoping, condition/target selection, audit log view.
APRIL backend needed later:
- Hook registration and event dispatch engine.
Phase strategy: Start as config editor + preview; execute hooks later.
5. Embedded Browser / Browser Use
Clone UI + interaction patterns:
- Viewport surface, toolbar, permissions prompts, screenshot capture flow, resize handles, permission status.
APRIL backend needed later:
- Browser automation service and sandboxing.
Phase strategy: For web, start with embedded iframe and controlled navigation; for desktop, use native webview integration later.
Phase 3 — APRIL backend adapters (2–4 weeks)
For each module, define an adapter boundary:
web/src/features/<feature>/
  components/
  state/
  adapters/
    april.ts   // APRIL backend API calls
    mock.ts    // temporary dummy backend
Recommended additions to FastAPI:
- /api/terminal/*
- /api/mcp/*
- /api/skills/*
- /api/hooks/*
- /api/browser/*
This keeps ZCode influence limited to UX and layout while APRIL remains the backend owner.
What I would not clone from ZCode
- Its provider/account/auth systems.
- Its storage and sync layers.
- Its runtime process management.
- Anything that duplicates APRIL’s harness/memory/session model.
Feature priority recommendation
If we want the biggest visual/functional payoff first:
1. Layout shell + inspector + command palette
2. MCP configurator UI with static config
3. Skills extractor UI with mock scanning
4. Terminal UI with mock sessions
5. Browser use UI (web-limited version)
6. Hooks UI as config-only