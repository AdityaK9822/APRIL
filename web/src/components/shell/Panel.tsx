import type { ReactNode } from 'react'

export function Panel({ title, children, className = '' }: {
  title?: string
  children: ReactNode
  className?: string
}) {
  return (
    <section className={`panel ${className}`}>
      {title && <header className="panel-head">{title}</header>}
      <div className="p-4">{children}</div>
    </section>
  )
}
