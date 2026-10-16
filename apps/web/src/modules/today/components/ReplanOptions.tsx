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
    <section aria-labelledby="options-heading" className="space-y-2">
      <div className="space-y-0.5">
        <h2 id="options-heading" className="text-sm font-semibold">
          Your reading does not fit yet
        </h2>
        <p className="text-[13px] text-muted-foreground">
          You are about {formatMinutes(event.shortfall_after)} short. Pick one, and we change nothing until you do.
        </p>
      </div>
      {event.options.length === 0 ? <Alert variant="info">There are no options to offer right now.</Alert> : null}
      <ul className="grid gap-2 md:grid-cols-2 xl:grid-cols-3">
        {event.options.map((raw) => {
          const view = optionView(raw)
          return (
            <li
              key={view.name}
              className="flex flex-col gap-1.5 rounded-lg border border-border bg-card p-3 shadow-soft"
            >
              <h3 className="text-[13px] font-medium">{view.title}</h3>
              <p className="text-[13px] text-muted-foreground">{view.detail}</p>
              <Button
                size="sm"
                className="mt-auto self-start"
                disabled={busy || !view.feasible}
                onClick={() => onChoose(view.name)}
              >
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
