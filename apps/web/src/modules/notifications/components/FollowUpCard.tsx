import { BellRing, Button } from '@artha/design-system'

import { AlertPreview } from './AlertPreview'
import { WRAP_BUTTON } from './classes'

interface Props {
  /** `ask`: the question. `done`: what happened, with Close. */
  stage: 'ask' | 'done'
  message: string
  enabling: boolean
  headingRef?: React.Ref<HTMLHeadingElement>
  onEnable: () => void
  onNotNow: () => void
  onClose: () => void
}

/**
 * The follow-up ask after a finished round: an inline card on the page, never a modal, with an equally easy way to say
 * no. It says what the student gets and that they can turn it off, and speaks the outcome in a polite live region.
 */
export function FollowUpCard({ stage, message, enabling, headingRef, onEnable, onNotNow, onClose }: Props) {
  return (
    <section
      aria-labelledby="followup-heading"
      className="space-y-4 rounded-2xl border border-border bg-card p-5 sm:p-6"
    >
      <h2 id="followup-heading" ref={headingRef} tabIndex={-1} className="text-lg font-bold outline-none">
        {stage === 'ask' ? 'Want to hear the next round end?' : 'Alerts'}
      </h2>
      {stage === 'ask' ? (
        <>
          <p>
            You just finished a round. Turn on alerts and the next one reaches you even when Artha is in the background
            or closed. Nothing else is sent, and you can turn alerts off any time in Settings.
          </p>
          <AlertPreview />
          <div className="flex flex-wrap items-center gap-3">
            <Button variant="cta" loading={enabling} onClick={onEnable} className={WRAP_BUTTON}>
              <BellRing aria-hidden /> Turn on alerts
            </Button>
            <Button variant="ghost" disabled={enabling} onClick={onNotNow}>
              Not now
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
