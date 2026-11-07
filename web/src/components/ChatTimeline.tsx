import { LoaderCircle } from 'lucide-react'
import { useChatStore } from '../store/chatStore'
import { MarkdownRenderer } from './MarkdownRenderer'

export function ChatTimeline() {
  const messages = useChatStore((s) => s.messages)

  return (
    <div className="flex-1 space-y-6 overflow-y-auto px-4 py-6">
      {messages.length === 0 && (
        <div className="text-shell-subtle mt-20 text-center">
          <div className="text-shell-foreground text-2xl font-light">APRIL Agent</div>
          <div className="mt-2 text-sm">Start a conversation to inspect the agent live.</div>
        </div>
      )}
      {messages.map((m) => (
        <div key={m.id} className={m.role === 'user' ? 'ml-auto max-w-2xl' : 'max-w-3xl'}>
          <div
            className={
              m.role === 'user'
                ? 'bg-shell-bubble text-shell-foreground rounded-2xl px-4 py-3 text-sm whitespace-pre-wrap'
                : 'text-sm'
            }
          >
            {m.role === 'user' ? (
              m.content
            ) : m.streaming && !m.content ? (
              <span className="text-shell-muted inline-flex items-center gap-2" role="status">
                <LoaderCircle
                  className="text-shell-accent-fg h-4 w-4 animate-spin motion-reduce:animate-none"
                  aria-hidden
                />
                Thinking…
              </span>
            ) : (
              <>
                <MarkdownRenderer content={m.content || ''} />
                {m.streaming && (
                  <span className="bg-shell-foreground ml-1 inline-block h-4 w-2 animate-pulse align-middle motion-reduce:animate-none" />
                )}
              </>
            )}
          </div>
        </div>
      ))}
    </div>
  )
}
