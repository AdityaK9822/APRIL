import { ChatTimeline } from '../../components/ChatTimeline'

export function ChatView() {
  return (
    <div className="flex flex-col flex-1 min-h-0">
      <div className="border-shell-border text-shell-subtle flex h-9 shrink-0 items-center gap-1 border-b px-3 text-xs">
        <span className="text-shell-muted font-medium">Conversation</span>
        <span aria-hidden>/</span>
        <span>Default Session</span>
        <span className="ml-auto">Chat is live</span>
      </div>
      <div className="flex flex-col flex-1 min-h-0">
        <ChatTimeline />
      </div>
    </div>
  )
}
