export const MODULES = [
  'Chat',
  'Skills',
  'MCP',
  'Hooks',
  'Terminal',
  'Browser',
  'Settings',
] as const

export type Module = (typeof MODULES)[number]

export function SidebarNav({
  active,
  onNavigate,
  collapsed,
}: {
  active: Module
  onNavigate: (m: Module) => void
  collapsed: boolean
}) {
  if (collapsed) return null
  return (
    <nav className="border-shell-border bg-shell-panel flex w-64 shrink-0 flex-col border-r">
      <div className="border-shell-border text-shell-subtle flex h-10 items-center justify-between border-b px-3">
        <span className="text-xs font-medium tracking-wider uppercase">Workspace</span>
      </div>
      <div className="space-y-1 p-2" role="tablist" aria-label="Workspace modules">
        {MODULES.map((module) => {
          const stubbed = module !== 'Chat'
          const isActive = active === module
          return (
            <button
              key={module}
              onClick={() => onNavigate(module)}
              aria-current={isActive ? 'page' : undefined}
              className={`flex h-9 w-full cursor-pointer items-center justify-between rounded-md px-3 text-sm outline-none transition-colors focus-visible:ring-2 focus-visible:ring-shell-ring ${
                isActive
                  ? 'bg-shell-hover font-medium text-shell-foreground'
                  : 'text-shell-muted hover:bg-shell-hover hover:text-shell-foreground'
              }`}
            >
              <span>{module}</span>
              <span className={`chip ${stubbed ? '' : 'chip-live'}`}>
                {stubbed ? 'Stub' : 'Live'}
              </span>
            </button>
          )
        })}
      </div>
      <div className="border-shell-border text-shell-subtle mt-auto border-t px-3 py-2 text-xs">
        Modules are shelled; backends come later.
      </div>
    </nav>
  )
}
