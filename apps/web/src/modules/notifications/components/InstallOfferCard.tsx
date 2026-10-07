import { Button, Download, motion, useReducedMotion } from '@artha/design-system'
import { useId } from 'react'

import type { InstallKind } from '../lib/install'
import { WRAP_BUTTON } from './classes'
import { InstallSteps } from './InstallSteps'

interface Props {
  kind: InstallKind
  /** The browser's install dialog is open. */
  busy: boolean
  onInstall: () => void
  /** Not now (the button offer) or Got it (the steps): either way the card goes away. */
  onClose: () => void
}

/**
 * The install offer on the focus page (X-01 W4.5, FR-C7): an inline card after a finished round, never a modal. Where
 * the browser can install in one click it is a button; on an iPhone, iPad or Mac Safari it shows how, because there is
 * no button to press. Presentational: the container decides when it shows.
 */
export function InstallOfferCard({ kind, busy, onInstall, onClose }: Props) {
  const headingId = useId()
  const reduce = useReducedMotion()
  return (
    <motion.section
      aria-labelledby={headingId}
      initial={reduce ? false : { opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4, ease: [0.22, 1, 0.36, 1] }}
      className="space-y-4 rounded-2xl border border-border bg-card p-5 shadow-soft sm:p-6"
    >
      <h2 id={headingId} className="text-lg font-bold">
        Keep Artha one tap away
      </h2>
      <p>
        Install it and Artha opens in its own window, with a small dot on its icon while a round is running. It takes a
        few seconds and you can remove it any time.
      </p>
      {kind === 'ios_steps' ? <InstallSteps /> : null}
      {kind === 'mac_safari' ? (
        <p>
          In Safari, choose <strong>File</strong>, then <strong>Add to Dock</strong>.
        </p>
      ) : null}
      <div className="flex flex-wrap items-center gap-3">
        {kind === 'prompt' ? (
          <>
            <Button variant="cta" loading={busy} onClick={onInstall} className={WRAP_BUTTON}>
              <Download aria-hidden /> Install Artha
            </Button>
            <Button variant="ghost" disabled={busy} onClick={onClose} className={WRAP_BUTTON}>
              Not now
            </Button>
          </>
        ) : (
          <Button variant="outline" onClick={onClose} className={WRAP_BUTTON}>
            Got it
          </Button>
        )}
      </div>
    </motion.section>
  )
}
