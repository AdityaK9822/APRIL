export function StatusBar({ items }: { items: Array<{ label: string; value: string }> }) {
  return (
    <footer className="border-shell-border bg-shell-panel/90 text-shell-subtle flex h-7 shrink-0 items-center gap-3 border-t px-3 text-[11px]">
      {items.map((item) => (
        <span key={item.label} className="inline-flex items-center gap-1">
          <span>{item.label}</span>
          <span className="text-shell-muted">{item.value}</span>
        </span>
      ))}
      <span className="ml-auto">APRIL</span>
    </footer>
  )
}
