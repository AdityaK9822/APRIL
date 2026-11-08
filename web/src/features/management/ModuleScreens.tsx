import { useEffect, useState } from 'react'
import { Panel } from '../../components/shell/Panel'
import { useThemeStore } from '../../store/themeStore'

const API_BASE = ''

interface BrowserState {
  session_id?: string
  url?: string
  title?: string
  text_preview?: string
  screenshot?: { format: string; base64: string }
}

function Field({
  label,
  value,
  onChange,
  placeholder,
}: {
  label: string
  value: string
  onChange: (value: string) => void
  placeholder?: string
}) {
  return (
    <label className="block space-y-1.5">
      <span className="field-label">{label}</span>
      <input
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        className="input"
      />
    </label>
  )
}

export function SkillsView() {
  const [query, setQuery] = useState('')
  const [items, setItems] = useState(['runtime-events', 'memory-context', 'tool-call-patterns'])
  const [title, setTitle] = useState('new-skill')
  const filtered = items.filter((item) => item.toLowerCase().includes(query.toLowerCase()))

  return (
    <div className="flex-1 min-h-0 space-y-4 overflow-y-auto p-4">
      <Panel title="Skills">
        <div className="grid gap-4 md:grid-cols-[1fr_2fr]">
          <div className="space-y-3">
            <Field label="Search" value={query} onChange={setQuery} placeholder="Filter skills" />
            <Field label="Create skill" value={title} onChange={setTitle} placeholder="skill-id" />
            <button
              onClick={() =>
                setItems((values) => (values.includes(title) ? values : [...values, title]))
              }
              disabled={!title.trim()}
              className="btn-primary w-full disabled:opacity-45"
            >
              Add stub skill
            </button>
          </div>
          <div className="space-y-2">
            {filtered.map((item) => (
              <div key={item} className="card-row">
                {item}
              </div>
            ))}
          </div>
        </div>
      </Panel>
    </div>
  )
}

export function McpView() {
  const [name, setName] = useState('')
  const [command, setCommand] = useState('')
  const [servers, setServers] = useState<Array<{ name: string; command: string; status: string }>>([
    { name: 'local-shell', command: 'python -m tools', status: 'Connected' },
  ])
  const [status, setStatus] = useState('Idle')

  return (
    <div className="flex-1 min-h-0 space-y-4 overflow-y-auto p-4">
      <Panel title="MCP Servers">
        <div className="grid gap-3 md:grid-cols-2">
          <Field label="Name" value={name} onChange={setName} placeholder="server-name" />
          <Field label="Command" value={command} onChange={setCommand} placeholder="node server.js" />
        </div>
        <div className="mt-3 flex gap-2">
          <button
            onClick={() => {
              if (name.trim()) {
                setServers((value) => [...value, { name, command, status: 'Pending' }])
                setName('')
                setCommand('')
                setStatus('Added; backend connection pending')
              }
            }}
            disabled={!name.trim()}
            className="btn-primary px-4 disabled:opacity-45"
          >
            Add server
          </button>
          <button
            onClick={() => setStatus('Connection test requires backend adapter')}
            className="btn-secondary px-4"
          >
            Test all
          </button>
        </div>
        <p className="hint mt-3" role="status" aria-live="polite">
          {status}
        </p>
        <div className="mt-4 space-y-2">
          {servers.map((server) => (
            <div key={server.name} className="card-row flex items-center justify-between">
              <span>{server.name}</span>
              <span className="hint">{server.status}</span>
            </div>
          ))}
        </div>
      </Panel>
    </div>
  )
}

export function HooksView() {
  const [events] = useState([
    'SessionStart',
    'UserPromptSubmit',
    'PreToolUse',
    'PostToolUse',
    'Stop',
  ])
  const [enabled, setEnabled] = useState<Record<string, boolean>>(
    Object.fromEntries(events.map((event) => [event, event !== 'Stop']))
  )

  return (
    <div className="flex-1 min-h-0 space-y-4 overflow-y-auto p-4">
      <Panel title="Hooks">
        {events.map((event) => (
          <label
            key={event}
            className="border-shell-border flex cursor-pointer items-center justify-between border-b py-2.5 last:border-b-0"
          >
            <span className="text-shell-muted text-sm">{event}</span>
            <input
              type="checkbox"
              checked={enabled[event]}
              onChange={() =>
                setEnabled((value) => ({ ...value, [event]: !value[event] }))
              }
              className="h-4 w-4"
            />
          </label>
        ))}
        <div className="border-shell-border text-shell-subtle mt-3 rounded-lg border border-dashed p-3 text-xs">
          Hook rules and execution log will be wired to the backend later.
        </div>
      </Panel>
    </div>
  )
}

export function TerminalView() {
  const [lines, setLines] = useState<string[]>(['APRIL terminal stub ready'])
  const [command, setCommand] = useState('')

  function run() {
    if (!command.trim()) return
    setLines((value) => [...value, `$ ${command}`, `Echo: ${command}`])
    setCommand('')
  }

  return (
    <div className="flex-1 min-h-0 space-y-4 overflow-y-auto p-4">
      <Panel title="Terminal">
        {/* Terminal canvas is deliberately always dark, in both themes */}
        <div className="terminal h-64 overflow-auto">
          {lines.map((line, index) => (
            <div key={index}>{line}</div>
          ))}
        </div>
        <div className="mt-3 flex gap-2">
          <input
            value={command}
            onChange={(e) => setCommand(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && run()}
            placeholder="Type and press Enter"
            aria-label="Terminal command"
            className="input flex-1"
          />
          <button onClick={run} disabled={!command.trim()} className="btn-secondary px-4 disabled:opacity-45">
            Run
          </button>
        </div>
      </Panel>
    </div>
  )
}

export function BrowserView() {
  const [url, setUrl] = useState('https://example.com')
  const [sessionId, setSessionId] = useState<string>('')
  const [status, setStatus] = useState('Initializing backend browser...')
  const [busy, setBusy] = useState(false)
  const [state, setState] = useState<BrowserState>({})

  useEffect(() => {
    let mounted = true
    async function openSession() {
      try {
        const response = await fetch(`${API_BASE}/api/browser/open`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ session_id: `web-${Math.random().toString(36).slice(2)}` }),
        })
        const data = await response.json()
        if (!mounted) return
        if (!response.ok) throw new Error(data.detail ?? `HTTP ${response.status}`)
        setSessionId(data.session_id)
        setState(data)
        setStatus(`Ready: ${data.title || 'Untitled page'}`)
      } catch (error) {
        if (mounted) {
          setStatus(error instanceof Error ? error.message : 'Browser backend unavailable')
        }
      }
    }
    void openSession()
    return () => {
      mounted = false
      if (sessionId) {
        void fetch(`${API_BASE}/api/browser/close`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ session_id: sessionId }),
        })
      }
    }
  }, [sessionId])

  async function navigate() {
    if (!sessionId || !url.trim()) return
    setBusy(true)
    setStatus('Navigating...')
    try {
      const response = await fetch(`${API_BASE}/api/browser/navigate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          session_id: sessionId,
          url,
          wait_until: 'domcontentloaded',
          timeout_ms: 30000,
        }),
      })
      const data = await response.json()
      if (!response.ok) throw new Error(data.detail ?? `HTTP ${response.status}`)
      setState(data)
      setStatus(`Loaded ${data.title || data.url}`)
      const screenshotResponse = await fetch(`${API_BASE}/api/browser/screenshot/${sessionId}`)
      if (screenshotResponse.ok) {
        const screenshot = await screenshotResponse.json()
        setState(screenshot)
      }
    } catch (error) {
      setStatus(error instanceof Error ? error.message : 'Navigation failed')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="flex-1 min-h-0 space-y-4 overflow-y-auto p-4">
      <Panel title="Browser">
        <div className="space-y-3">
          <div className="flex gap-2">
            <input
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              aria-label="Page URL"
              className="input flex-1"
            />
            <button
              onClick={() => void navigate()}
              disabled={!sessionId || busy || !url.trim()}
              className="btn-primary px-4 disabled:opacity-45"
            >
              {busy ? 'Navigating…' : 'Navigate'}
            </button>
          </div>
          <p className="hint" role="status" aria-live="polite">
            {status}
          </p>
          <div className="border-shell-border bg-shell-card text-shell-subtle flex h-96 items-center justify-center overflow-hidden rounded-lg border">
            {state.screenshot?.base64 ? (
              <img
                src={`data:image/png;base64,${state.screenshot.base64}`}
                alt={`Browser screenshot${state.title ? ` for ${state.title}` : ''}`}
                className="h-full w-full object-contain"
              />
            ) : (
              <div className="text-sm">No page loaded yet.</div>
            )}
          </div>
          {state.text_preview && (
            <details className="text-shell-subtle text-xs">
              <summary className="text-shell-muted cursor-pointer">
                Extracted text preview
              </summary>
              <pre className="mt-2 break-words whitespace-pre-wrap">{state.text_preview}</pre>
            </details>
          )}
        </div>
      </Panel>
    </div>
  )
}

export function SettingsView() {
  const [model, setModel] = useState('gemma4:31b-cloud')
  const [logs, setLogs] = useState(true)
  const theme = useThemeStore((s) => ({ theme: s.theme, toggle: s.toggle }))

  return (
    <div className="flex-1 min-h-0 space-y-4 overflow-y-auto p-4">
      <Panel title="Settings">
        <Field label="Default model" value={model} onChange={setModel} />
        <div className="mt-4 space-y-3">
          <label className="text-shell-muted flex min-h-9 cursor-pointer items-center justify-between gap-3 text-sm">
            Dark mode
            <input
              type="checkbox"
              checked={theme.theme === 'dark'}
              onChange={theme.toggle}
            />
          </label>
          <label className="text-shell-muted flex min-h-9 cursor-pointer items-center justify-between gap-3 text-sm">
            Show inspector logs
            <input type="checkbox" checked={logs} onChange={() => setLogs((v) => !v)} />
          </label>
        </div>
      </Panel>
    </div>
  )
}
