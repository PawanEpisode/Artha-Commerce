import { Alert, Button } from '@artha/design-system'

import { optionView } from '../lib/planner'
import type { OptionChoice, ReplanEvent } from '../lib/planner-types'
import { formatMinutes } from '../lib/time'

/**
 * The three ways out when the plan does not fit (FR-F13-49). Nothing here changes the plan until the student taps one; "Keep my
 * plan" records that they looked and chose to carry on.
 */
export function ReplanOptions({
  event,
  busy,
  onChoose,
}: {
  event: ReplanEvent
  busy: boolean
  onChoose: (option: OptionChoice) => void
}) {
  return (
    <section aria-labelledby="options-heading" className="space-y-3">
      <div className="space-y-1">
        <h2 id="options-heading" className="font-display text-lg font-bold">
          Your reading does not fit yet
        </h2>
        <p className="text-sm text-muted-foreground">
          You are about {formatMinutes(event.shortfall_after)} short. Pick one, and we change nothing until you do.
        </p>
      </div>
      {event.options.length === 0 ? <Alert variant="info">There are no options to offer right now.</Alert> : null}
      <ul className="space-y-3">
        {event.options.map((raw) => {
          const view = optionView(raw)
          return (
            <li key={view.name} className="space-y-2 rounded-xl border border-border bg-card p-4">
              <h3 className="font-medium">{view.title}</h3>
              <p className="text-sm text-muted-foreground">{view.detail}</p>
              <Button disabled={busy || !view.feasible} onClick={() => onChoose(view.name)}>
                {view.confirm}
              </Button>
            </li>
          )
        })}
      </ul>
      <Button variant="ghost" size="sm" disabled={busy} onClick={() => onChoose('none')}>
        Keep my plan as it is
      </Button>
    </section>
  )
}
