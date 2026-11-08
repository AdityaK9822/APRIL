import { Panel } from './Panel'

export function PlaceholderFeature({
  title,
  description,
  details,
}: {
  title: string
  description: string
  details: string[]
}) {
  return (
    <div className="flex-1 min-h-0 p-4 overflow-y-auto">
      <Panel title={title}>
        <div className="space-y-3">
          <p className="text-shell-muted text-sm">{description}</p>
          <div className="grid gap-3 md:grid-cols-2">
            {details.map((detail) => (
              <div key={detail} className="card-row text-xs">
                {detail}
              </div>
            ))}
          </div>
          <div className="border-shell-border text-shell-subtle rounded-lg border border-dashed p-3 text-xs">
            Stubbed surface. Interaction will be wired after the backend adapter is ready.
          </div>
        </div>
      </Panel>
    </div>
  )
}