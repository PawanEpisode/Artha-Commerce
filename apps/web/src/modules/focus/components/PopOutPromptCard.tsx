import { Button, Checkbox, Label, motion, Pause, PictureInPicture2, useReducedMotion } from '@artha/design-system'
import { useEffect, useId, useState } from 'react'

interface Props {
  /** The "Do this every time I start a round" box. */
  always: boolean
  onAlwaysChange: (always: boolean) => void
  onPopOut: () => void
  onNotNow: () => void
}

const SAID =
  'Tip: you can keep the timer on top of your other windows while you study. The choices are below the timer.'

/** A drawing of the pill the student is about to get. Decorative: the heading and the buttons say everything. */
function PillPreview() {
  return (
    <div
      aria-hidden
      className="flex shrink-0 items-center gap-3 rounded-full border border-input bg-card px-4 py-2 shadow-soft"
    >
      <span className="size-2 rounded-full bg-primary" />
      <span className="text-base font-bold tabular-nums">24:12</span>
      <span className="grid size-7 place-items-center rounded-full bg-secondary text-foreground">
        <Pause className="size-3.5" />
      </span>
    </div>
  )
}

/**
 * The one-time offer to pop the timer out (X-01 W4.3), shown inline under the focus card while a round runs. It is not a
 * modal and never takes focus: the student keeps studying and answers when ready. It is announced once, politely.
 * Presentational: the container decides when it shows and what the answers do.
 */
export function PopOutPromptCard({ always, onAlwaysChange, onPopOut, onNotNow }: Props) {
  const headingId = useId()
  const boxId = useId()
  const reduce = useReducedMotion()
  // The live region exists first and gets its text a moment later, which is what makes screen readers say it.
  const [said, setSaid] = useState('')
  useEffect(() => setSaid(SAID), [])

  return (
    <motion.section
      aria-labelledby={headingId}
      initial={reduce ? false : { opacity: 0, y: 12, scale: 0.98 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      transition={{ duration: 0.45, ease: [0.22, 1, 0.36, 1] }}
      className="space-y-4 rounded-2xl border border-border bg-card p-5 shadow-soft sm:p-6"
    >
      <div className="flex flex-wrap items-center gap-x-5 gap-y-3">
        <div className="min-w-0 flex-1 basis-56 space-y-1">
          <h2 id={headingId} className="text-lg font-bold">
            Keep the timer on top while you study?
          </h2>
          <p className="text-sm text-muted-foreground">
            A small window that stays above your notes and PDFs, so the clock is always in sight. Closing it never stops
            the round.
          </p>
        </div>
        <PillPreview />
      </div>

      <div className="flex items-start gap-3">
        <Checkbox id={boxId} checked={always} onCheckedChange={(v) => onAlwaysChange(v === true)} />
        <Label htmlFor={boxId} className="text-sm font-medium">
          Do this every time I start a round
        </Label>
      </div>

      <div className="flex flex-wrap items-center gap-3">
        <Button variant="cta" onClick={onPopOut} className="h-auto min-h-11 max-w-full py-2.5 whitespace-normal">
          <PictureInPicture2 aria-hidden /> Pop out
        </Button>
        <Button variant="ghost" onClick={onNotNow} className="h-auto min-h-11 max-w-full py-2.5 whitespace-normal">
          Not now
        </Button>
      </div>

      <p role="status" aria-live="polite" className="sr-only">
        {said}
      </p>
    </motion.section>
  )
}
