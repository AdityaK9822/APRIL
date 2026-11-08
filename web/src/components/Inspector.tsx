import { useChatStore } from '../store/chatStore'

export function Inspector() {
  const events = useChatStore((s) => s.inspector)
  const clear = () => useChatStore.setState({ inspector: [] })

  return (
    <div className="flex h-full flex-col">
      <div className="border-shell-border flex items-center justify-between border-b px-3 py-2">
        <span className="text-shell-subtle text-xs font-medium tracking-wider uppercase">
          Inspector
        </span>
        <button onClick={clear} className="btn btn-ghost h-7 px-2 text-xs">
          Clear
        </button>
      </div>
      <div className="font-mono space-y-1 flex-1 overflow-y-auto p-2 text-[11px] leading-4">
        {events.length === 0 && (
          <div className="text-shell-subtle italic">No events yet.</div>
        )}
        {events.map((e) => (
          <div
            key={e.id}
            className="border-shell-border bg-shell-card text-shell-muted rounded border px-2 py-1"
          >
            <span className="text-shell-subtle">{e.timestamp?.slice(11, 19) ?? ''}</span>{' '}
            <span className="text-shell-accent-fg">{e.type}</span>{' '}
            <span className="text-shell-foreground">{e.summary}</span>
          </div>
        ))}
      </div>
    </div>
  )
}
