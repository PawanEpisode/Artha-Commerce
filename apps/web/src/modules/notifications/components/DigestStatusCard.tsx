import { BellRing, Button } from '@artha/design-system'

import { WRAP_BUTTON } from './classes'

interface Props {
  time: string
  busy: boolean
  headingRef?: React.Ref<HTMLHeadingElement>
  onStop: () => void
}

/** Settings, while the daily digest is on (W3.7): what the student gets, and the way back to separate alerts. */
export function DigestStatusCard({ time, busy, headingRef, onStop }: Props) {
  return (
    <section aria-labelledby="digest-status-heading" className="space-y-4 rounded-2xl border border-border bg-card p-6">
      <h2 id="digest-status-heading" ref={headingRef} tabIndex={-1} className="text-lg font-bold outline-none">
        Daily digest is on
      </h2>
      <p>
        You get one alert a day at <strong>{time}</strong> (your daily nudge time) with what is new and what is due.
        Timer alerts still reach you; everything else waits in your inbox.
      </p>
      <Button variant="outline" loading={busy} onClick={onStop} className={WRAP_BUTTON}>
        <BellRing aria-hidden /> Switch back to separate alerts
      </Button>
    </section>
  )
}
