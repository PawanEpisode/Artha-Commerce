import { Button, Clock } from '@artha/design-system'

import { WRAP_BUTTON } from './classes'

interface Props {
  /** `offer`: the question. `done`: what happened, with Close. */
  stage: 'offer' | 'done'
  /** When the digest would arrive, `HH:MM` in the student's time zone (their nudge time). */
  time: string
  message: string
  busy: boolean
  headingRef?: React.Ref<HTMLHeadingElement>
  onAccept: () => void
  onDecline: () => void
  onClose: () => void
}

/**
 * The fatigue offer (W3.7, FR-N34): an inline card, never a modal, with an equally easy way to say no. It says what
 * changes (one alert a day, the timer still alerts, everything else waits in the inbox) and how to undo it, then speaks
 * the outcome in a polite live region.
 */
export function DigestOfferCard({ stage, time, message, busy, headingRef, onAccept, onDecline, onClose }: Props) {
  return (
    <section
      aria-labelledby="digest-offer-heading"
      className="space-y-4 rounded-2xl border border-border bg-card p-5 sm:p-6"
    >
      <h2 id="digest-offer-heading" ref={headingRef} tabIndex={-1} className="text-lg font-bold outline-none">
        {stage === 'offer' ? 'Fewer alerts, one daily digest?' : 'Daily digest'}
      </h2>
      {stage === 'offer' ? (
        <>
          <p>
            Your last few alerts went unopened. Switch to one digest a day at <strong>{time}</strong> with what is new
            and what is due. Timer alerts still reach you, and everything else waits in your inbox. You can switch back
            any time in Settings.
          </p>
          <div className="flex flex-wrap items-center gap-3">
            <Button variant="cta" loading={busy} onClick={onAccept} className={WRAP_BUTTON}>
              <Clock aria-hidden /> Switch to a daily digest
            </Button>
            <Button variant="ghost" disabled={busy} onClick={onDecline} className={WRAP_BUTTON}>
              Keep separate alerts
            </Button>
          </div>
        </>
      ) : (
        <div className="flex flex-wrap items-center gap-3">
          <p className="min-w-0 flex-1">{message}</p>
          <Button variant="outline" onClick={onClose}>
            Close
          </Button>
        </div>
      )}
      <p role="status" aria-live="polite" className="sr-only">
        {stage === 'done' ? message : ''}
      </p>
    </section>
  )
}
