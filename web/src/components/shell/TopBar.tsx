import type { ReactNode } from 'react'

export function TopBar({ left, center, right }: {
  left: ReactNode
  center: ReactNode
  right: ReactNode
}) {
  return (
    <header className="border-shell-border bg-shell-panel/90 flex h-12 shrink-0 items-center gap-2 border-b px-3 backdrop-blur">
      <div className="flex items-center gap-2">{left}</div>
      <div className="text-shell-subtle hidden items-center gap-2 text-xs md:flex">{center}</div>
      <div className="ml-auto flex items-center gap-2">{right}</div>
    </header>
  )
}
