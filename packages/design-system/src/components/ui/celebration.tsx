import * as React from 'react'

import { CircleCheck } from '../../icons'
import { Button } from './button'

export interface CelebrationProps {
  title: string
  /** One personal line, e.g. "Aarav, CMA Final June 2027 is set up. 238 days to go." */
  message: string
  ctaLabel: string
  onContinue: () => void
  /** Moves on by itself after this many milliseconds. 0 disables it. Default 2500. */
  autoContinueMs?: number
}

const reducedMotion = () =>
  typeof window !== 'undefined' && !!window.matchMedia?.('(prefers-reduced-motion: reduce)').matches

/**
 * Full-screen "all set" panel with one confetti burst. The confetti library loads only now (dynamic import, so it
 * never ships in the main bundle) and not at all under reduced motion, where the panel is static and the message is
 * announced politely instead.
 */
export function Celebration({ title, message, ctaLabel, onContinue, autoContinueMs = 2500 }: CelebrationProps) {
  const cta = React.useRef<HTMLButtonElement>(null)
  const done = React.useRef(false)
  const still = reducedMotion()

  const finish = React.useCallback(() => {
    if (done.current) return
    done.current = true
    onContinue()
  }, [onContinue])

  React.useEffect(() => {
    cta.current?.focus()
    if (!still) {
      void import('canvas-confetti')
        .then(({ default: confetti }) => {
          void confetti({ particleCount: 90, spread: 70, origin: { y: 0.6 }, disableForReducedMotion: true })
        })
        .catch(() => undefined) // a missing burst never blocks the student
    }
    if (autoContinueMs <= 0) return
    const timer = window.setTimeout(finish, autoContinueMs)
    return () => window.clearTimeout(timer)
  }, [autoContinueMs, finish, still])

  return (
    <div
      data-slot="celebration"
      role="dialog"
      aria-modal="true"
      aria-labelledby="celebration-title"
      className="fixed inset-0 z-50 grid place-items-center bg-background p-6"
    >
      <div className="max-w-md space-y-5 text-center">
        <CircleCheck
          aria-hidden
          className="mx-auto size-16 text-success motion-safe:animate-in motion-safe:duration-500 motion-safe:zoom-in-50"
        />
        <h1 id="celebration-title" className="font-display text-3xl font-extrabold">
          {title}
        </h1>
        <p role="status" className="text-lg text-muted-foreground">
          {message}
        </p>
        <Button ref={cta} size="lg" onClick={finish}>
          {ctaLabel}
        </Button>
      </div>
    </div>
  )
}

export interface CelebrateProps {
  /** Fires one burst when this turns true, and never again until it has been false. */
  active: boolean
  /** Announced politely, e.g. "Day complete". Always rendered, so reduced-motion and screen-reader users get it too. */
  message: string
  className?: string
}

/**
 * The small in-place celebration (Today's "day complete"): one confetti burst on the transition to `active`, a polite
 * status line, no overlay and no focus change. Nothing moves under reduced motion; the message still announces.
 */
export function Celebrate({ active, message, className }: CelebrateProps) {
  const fired = React.useRef(false)
  React.useEffect(() => {
    if (!active) {
      fired.current = false
      return
    }
    if (fired.current || reducedMotion()) return
    fired.current = true
    void import('canvas-confetti')
      .then(({ default: confetti }) => {
        void confetti({ particleCount: 60, spread: 60, origin: { y: 0.4 }, disableForReducedMotion: true })
      })
      .catch(() => undefined)
  }, [active])
  return (
    <p data-slot="celebrate" role="status" className={className}>
      {active ? message : ''}
    </p>
  )
}
