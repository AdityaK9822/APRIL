import { useEffect, useRef, useState } from 'react'
import type { ReactNode } from 'react'
import type { Module } from './components/shell/SidebarNav'
import { SidebarNav } from './components/shell/SidebarNav'
import { TopBar } from './components/shell/TopBar'
import { StatusBar } from './components/shell/StatusBar'
import { ThemeToggle } from './components/shell/ThemeToggle'
import { ChatView } from './features/chat/ChatView'
import {
  SkillsView,
  McpView,
  HooksView,
  TerminalView,
  BrowserView,
  SettingsView,
} from './features/management/ModuleScreens'
import { LoaderCircle, PanelLeftClose, PanelLeftOpen } from 'lucide-react'
import { useChatStore } from './store/chatStore'
import { Inspector } from './components/Inspector'
import './index.css'

const API_BASE = ''

interface SseEvent {
  type: string
  payload?: unknown
  content?: string
  timestamp?: string
  id?: string
}

function newId() {
  return Math.random().toString(36).slice(2)
}

const MODULE_VIEWS: Record<Module, ReactNode> = {
  Chat: <ChatView />,
  Skills: <SkillsView />,
  MCP: <McpView />,
  Hooks: <HooksView />,
  Terminal: <TerminalView />,
  Browser: <BrowserView />,
  Settings: <SettingsView />,
}

function summarize(type: string, payload: unknown): string {
  const p = (payload ?? {}) as Record<string, unknown>
  switch (type) {
    case 'log':
      return `[${p.level ?? 'INFO'}] [${p.source ?? '?'}] ${p.message ?? ''}`
    case 'tool_call.start':
      return `tool_call.start ${p.tool_name ?? ''} ${JSON.stringify(p.tool_args ?? {})}`
    case 'tool_call.output':
      return `tool output ${String(p.text ?? '').slice(0, 120)}`
    case 'tool_call.done':
      return `tool done ${p.tool_name ?? ''}: ${String(p.result ?? '').slice(0, 120)}`
    case 'status':
      return `status: ${p.status ?? ''}`
    case 'error':
      return `ERROR ${p.error_type ?? ''}: ${p.message ?? ''}`
    case 'message.delta':
      return `delta: ${String((p as { content?: string }).content ?? '').slice(0, 80)}`
    default:
      return type
  }
}

export default function App() {
  const [activeModule, setActiveModule] = useState<Module>('Chat')
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false)
  const [inspectorOpen, setInspectorOpen] = useState(true)
  const [input, setInput] = useState('')
  const [busy, setBusy] = useState(false)
  const [inspectorTab, setInspectorTab] = useState<'logs' | 'tools' | 'context'>('logs')

  const inputRef = useRef<HTMLTextAreaElement>(null)
  const chatScrollRef = useRef<HTMLDivElement>(null)

  const {
    status,
    addMessage,
    appendToken,
    finalizeMessage,
    addInspectorEvent,
    setStatus,
  } = useChatStore()

  useEffect(() => {
    const es = new EventSource(`${API_BASE}/api/events`)
    const handler = (ev: MessageEvent) => {
      try {
        const data = JSON.parse(ev.data) as SseEvent
        addInspectorEvent({
          id: data.id ?? newId(),
          type: data.type,
          timestamp: data.timestamp,
          summary: summarize(data.type, data.payload),
          payload: data.payload,
        })
        if (data.type === 'status') {
          const s = (data.payload as { status?: string } | null)?.status
          if (s) setStatus(s)
        }
      } catch {
        /* ignore malformed events */
      }
    }
    const names = [
      'connected',
      'message.delta',
      'message.start',
      'message.done',
      'tool_call.start',
      'tool_call.output',
      'tool_call.done',
      'log',
      'error',
      'status',
      'session',
    ]
    names.forEach((name) => es.addEventListener(name, handler as EventListener))
    es.onerror = () => { /* browser reconnect */ }
    return () => es.close()
  }, [addInspectorEvent, setStatus])

  async function send() {
    const text = input.trim()
    if (!text || busy) return
    setInput('')
    setBusy(true)
    addMessage({ id: newId(), role: 'user', content: text })
    const assistantId = newId()
    addMessage({ id: assistantId, role: 'assistant', content: '', streaming: true })
    setStatus('thinking')

    try {
      const res = await fetch(`${API_BASE}/api/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: text }),
      })
      if (!res.ok || !res.body) throw new Error(`HTTP ${res.status}`)
      const reader = res.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''
      while (true) {
        const { value, done } = await reader.read()
        if (done) break
        buffer += decoder.decode(value, { stream: true })
        const chunks = buffer.split('\n\n')
        buffer = chunks.pop() ?? ''
        for (const chunk of chunks) {
          const lines = chunk.split('\n')
          let eventName = 'message'
          let data = ''
          for (const line of lines) {
            if (line.startsWith('event:')) eventName = line.slice(6).trim()
            else if (line.startsWith('data:')) data += line.slice(5).trim()
          }
          if (!data) continue
          let parsed: SseEvent
          try {
            parsed = JSON.parse(data) as SseEvent
          } catch {
            continue
          }
          if (eventName === 'message.delta') {
            const token =
              (parsed.payload as { content?: string })?.content ?? parsed.content ?? ''
            appendToken(assistantId, token)
          } else if (eventName === 'chat.done' || eventName === 'message.done') {
            finalizeMessage(assistantId)
          } else if (eventName === 'error') {
            const message = (parsed.payload as { message?: string })?.message ?? 'error'
            appendToken(assistantId, `\n\n⚠️ ${message}`)
            finalizeMessage(assistantId)
          }
        }
      }
      finalizeMessage(assistantId)
    } catch (err) {
      appendToken(
        assistantId,
        `\n\n⚠️ ${err instanceof Error ? err.message : String(err)}`
      )
      finalizeMessage(assistantId)
    } finally {
      setBusy(false)
      chatScrollRef.current?.scrollTo({
        top: chatScrollRef.current.scrollHeight,
        behavior: 'smooth',
      })
    }
  }

  function handleKey(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      void send()
    }
  }

  return (
    <div className="bg-shell text-shell-foreground h-screen w-screen flex flex-col overflow-hidden">
      <a
        href="#main-content"
        className="sr-only focus:not-sr-only focus:fixed focus:top-2 focus:left-2 focus:z-50 focus:px-3 focus:py-2 focus:bg-shell-accent focus:text-white focus:rounded"
      >
        Skip to main content
      </a>
      <TopBar
        left={
          <>
            <button
              onClick={() => setSidebarCollapsed((v) => !v)}
              className="btn btn-ghost btn-icon"
              aria-label={sidebarCollapsed ? 'Expand sidebar' : 'Collapse sidebar'}
            >
              {sidebarCollapsed ? (
                <PanelLeftClose className="h-4 w-4" aria-hidden />
              ) : (
                <PanelLeftOpen className="h-4 w-4" aria-hidden />
              )}
            </button>
            <span className="font-semibold text-sm tracking-tight">APRIL Agent</span>
            <span className="chip chip-card hidden md:inline-flex text-[11px]">
              {activeModule}
            </span>
          </>
        }
        center={
          <>
            <span className="text-shell-muted font-medium">{activeModule}</span>
            <span aria-hidden>/</span>
            <span>Workspace</span>
          </>
        }
        right={
          <>
            <label className="sr-only" htmlFor="global-palette">
              Command palette
            </label>
            <button
              id="global-palette"
              aria-label="Open command palette"
              className="btn btn-secondary hidden h-8 px-3 text-xs md:inline-flex"
            >
              ⌘K Command palette
            </button>
            <div
              className="chip chip-card"
              role="status"
              aria-live="polite"
            >
              {status}
            </div>
            <ThemeToggle />
            <button
              onClick={() => setInspectorOpen((v) => !v)}
              aria-label={inspectorOpen ? 'Collapse inspector' : 'Expand inspector'}
              className="btn btn-secondary h-8 px-3 text-xs"
            >
              {inspectorOpen ? 'Inspector' : 'Show inspector'}
            </button>
          </>
        }
      />

      <div className="flex-1 min-h-0 flex">
        <aside
          className={`shrink-0 overflow-hidden border-shell-border bg-shell-panel border-r transition-[width,opacity] duration-200 ease-out motion-reduce:transition-none ${
            sidebarCollapsed
              ? 'w-0 opacity-0 border-r-0 pointer-events-none'
              : 'w-64 opacity-100'
          }`}
          aria-hidden={sidebarCollapsed}
        >
          <SidebarNav
            active={activeModule}
            onNavigate={setActiveModule}
            collapsed={false}
          />
        </aside>

        <main id="main-content" className="flex-1 min-w-0 flex flex-col bg-shell" role="main">
          {activeModule === 'Chat' ? (
            <>
              <div ref={chatScrollRef} className="flex-1 min-h-0 flex flex-col">
                <ChatView />
              </div>
              <div className="shrink-0 border-shell-border border-t p-3">
                <div className="max-w-4xl mx-auto flex gap-2 items-end">
                  <textarea
                    ref={inputRef}
                    value={input}
                    onChange={(e) => setInput(e.target.value)}
                    onKeyDown={handleKey}
                    placeholder="Message APRIL… (Enter to send, Shift+Enter for newline)"
                    aria-label="Message APRIL"
                    rows={2}
                    className="input flex-1 resize-none rounded-md py-2"
                  />
                  <button
                    onClick={() => void send()}
                    disabled={busy || !input.trim()}
                    aria-label={busy ? 'Working' : 'Send message'}
                    className="btn-primary min-w-[6.5rem] px-4"
                  >
                    {busy ? (
                      <>
                        <LoaderCircle
                          className="h-4 w-4 animate-spin motion-reduce:animate-none"
                          aria-hidden
                        />
                        Thinking…
                      </>
                    ) : (
                      'Send'
                    )}
                  </button>
                </div>
              </div>
            </>
          ) : (
            <ModuleHeader module={activeModule} />
          )}

          <div className={activeModule === 'Chat' ? 'hidden' : 'flex-1 min-h-0'}>
            {MODULE_VIEWS[activeModule]}
          </div>
        </main>

        <aside
          className={`shrink-0 overflow-hidden border-shell-border bg-shell-panel border-l flex flex-col transition-[width,opacity] duration-200 ease-out motion-reduce:transition-none ${
            inspectorOpen ? 'w-96 opacity-100' : 'w-0 opacity-0 border-l-0 pointer-events-none'
          }`}
          aria-hidden={!inspectorOpen}
        >
          <div style={{ width: '24rem' }} className="shrink-0 flex flex-col h-full">
            <div className="h-10 px-3 flex items-center gap-2 border-shell-border border-b">
              {(['logs', 'tools', 'context'] as const).map((tab) => (
                <button
                  key={tab}
                  onClick={() => setInspectorTab(tab)}
                  className={`tab ${inspectorTab === tab ? 'tab-active' : ''}`}
                >
                  {tab}
                </button>
              ))}
            </div>
            <div className="flex-1 min-h-0">
              {inspectorTab === 'logs' ? (
                <Inspector />
              ) : (
                <div className="hint p-4">
                  {inspectorTab === 'tools'
                    ? 'Tool-call inspection will live here. Stubbed until tool execution metadata is wired.'
                    : 'Session context inspection will live here. Wired to /api/context soon.'}
                </div>
              )}
            </div>
          </div>
        </aside>
      </div>

      <StatusBar
        items={[
          { label: 'Module', value: activeModule },
          { label: 'Backend', value: 'Local FastAPI' },
          { label: 'Inspector', value: inspectorOpen ? 'Live SSE' : 'Closed' },
        ]}
      />
    </div>
  )
}

function ModuleHeader({ module }: { module: Module }) {
  return (
    <div className="border-shell-border text-shell-subtle flex h-9 shrink-0 items-center gap-1 border-b px-3 text-xs">
      <span className="text-shell-muted font-medium">{module}</span>
      <span aria-hidden>/</span>
      <span>Workspace</span>
      <span className="ml-auto">Feature shell (backend pending)</span>
    </div>
  )
}