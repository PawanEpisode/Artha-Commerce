import { useMotionValueEvent, useReducedMotion, useScroll } from 'motion/react'
import { type KeyboardEvent as ReactKeyboardEvent, type ReactNode, useCallback, useId, useRef, useState } from 'react'

import { stickyStepIndex, stickyStepScrollProgress } from '../../lib/sticky-story'
import { cn } from '../../lib/utils'

export interface StickyStoryStep {
  id: string
  /** Short label in the rail / jump list. */
  rail: ReactNode
  content: ReactNode
  media: ReactNode
}

export interface StickyStoryProps {
  /** Accessible name of the walkthrough, e.g. "Workspace tools". */
  label: string
  steps: ReadonlyArray<StickyStoryStep>
  /** Viewport-heights of scroll per step on the pinned layout. */
  stepVh?: number
  className?: string
}

const headerTop = 'top-[var(--site-header-height,0px)]'
const headerOffset = 'scroll-mt-[var(--site-header-height,0px)]'
const panelHeight = 'h-[calc(100svh-var(--site-header-height,0px))]'

function JumpList({
  label,
  steps,
  className,
}: {
  label: string
  steps: ReadonlyArray<StickyStoryStep>
  className?: string
}) {
  return (
    <nav aria-label={label} className={cn('mb-8', className)}>
      <ol className="flex gap-2 overflow-x-auto overscroll-x-contain pb-1 [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
        {steps.map((step) => (
          <li key={step.id} className="shrink-0">
            <a
              href={`#${step.id}`}
              className="inline-flex h-11 max-w-56 items-center rounded-full border border-border bg-card px-4 text-sm font-semibold text-foreground outline-none focus-visible:ring-[3px] focus-visible:ring-ring/40"
            >
              {step.rail}
            </a>
          </li>
        ))}
      </ol>
    </nav>
  )
}

function StackedSteps({ steps }: { steps: ReadonlyArray<StickyStoryStep> }) {
  return (
    <div className="space-y-12 sm:space-y-16">
      {steps.map((step) => (
        <section key={step.id} id={step.id} className={cn(headerOffset, 'grid gap-8 lg:grid-cols-2 lg:items-center')}>
          <div>{step.content}</div>
          <div>{step.media}</div>
        </section>
      ))}
    </div>
  )
}

function StickyTrack({
  label,
  steps,
  stepVh,
}: {
  label: string
  steps: ReadonlyArray<StickyStoryStep>
  stepVh: number
}) {
  const track = useRef<HTMLDivElement>(null)
  const buttons = useRef<Array<HTMLButtonElement | null>>([])
  const holding = useRef<number | null>(null)
  const holdTimer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined)
  const stepRef = useRef(0)
  const [step, setStep] = useState(0)
  const panelId = useId()
  const count = steps.length
  const { scrollYProgress } = useScroll({ target: track, offset: ['start start', 'end end'] })

  useMotionValueEvent(scrollYProgress, 'change', (progress) => {
    const held = holding.current
    const next = stickyStepIndex(progress, count, stepRef.current)
    if (held !== null) {
      if (next === held) holding.current = null
      return
    }
    if (next !== stepRef.current) {
      stepRef.current = next
      setStep(next)
    }
  })

  const goTo = useCallback(
    (index: number) => {
      const el = track.current
      if (!el) return
      const i = Math.min(count - 1, Math.max(0, index))
      holding.current = i
      if (holdTimer.current) window.clearTimeout(holdTimer.current)
      holdTimer.current = setTimeout(() => {
        holding.current = null
      }, 700)
      stepRef.current = i
      setStep(i)
      const top = el.getBoundingClientRect().top + window.scrollY
      const range = Math.max(1, el.offsetHeight - window.innerHeight)
      window.scrollTo({ top: top + stickyStepScrollProgress(i, count) * range, behavior: 'smooth' })
      buttons.current[i]?.focus()
    },
    [count],
  )

  const onRailKey = (event: ReactKeyboardEvent<HTMLButtonElement>) => {
    if (count === 0) return
    const keys: Record<string, number> = {
      ArrowDown: Math.min(count - 1, step + 1),
      ArrowRight: Math.min(count - 1, step + 1),
      ArrowUp: Math.max(0, step - 1),
      ArrowLeft: Math.max(0, step - 1),
      Home: 0,
      End: count - 1,
    }
    const next = keys[event.key]
    if (next === undefined) return
    event.preventDefault()
    goTo(next)
  }

  const active = steps[step]
  if (!active) return null

  return (
    <div ref={track} className="relative" style={{ height: `${count * stepVh}vh` }}>
      <div
        className={cn(
          'sticky grid items-stretch gap-6 py-6 lg:grid-cols-[minmax(9rem,12rem)_minmax(0,1fr)_minmax(14rem,20rem)] xl:grid-cols-[minmax(12rem,15rem)_minmax(0,1fr)_minmax(16rem,22rem)] xl:gap-8',
          headerTop,
          panelHeight,
        )}
      >
        <nav aria-label={label} className="min-h-0 overflow-y-auto py-2">
          <ol className="flex flex-col gap-1">
            {steps.map((item, i) => {
              const current = i === step
              return (
                <li key={item.id}>
                  <button
                    ref={(node) => {
                      buttons.current[i] = node
                    }}
                    type="button"
                    aria-current={current ? 'true' : undefined}
                    aria-controls={panelId}
                    tabIndex={current ? 0 : -1}
                    onClick={() => goTo(i)}
                    onKeyDown={onRailKey}
                    className={cn(
                      'flex min-h-11 w-full cursor-pointer items-center rounded-xl px-3 text-left text-sm font-semibold transition-colors outline-none motion-reduce:transition-none',
                      'focus-visible:ring-[3px] focus-visible:ring-ring/40',
                      current
                        ? 'bg-primary text-primary-foreground shadow-soft'
                        : 'text-muted-foreground hover:bg-muted hover:text-foreground',
                    )}
                  >
                    {item.rail}
                  </button>
                </li>
              )
            })}
          </ol>
        </nav>
        <div
          id={panelId}
          aria-live="polite"
          className="flex min-h-0 min-w-0 flex-col justify-start overflow-y-auto py-2"
        >
          {active.content}
        </div>
        <div aria-hidden className="flex min-h-0 min-w-0 items-start overflow-y-auto py-2">
          {active.media}
        </div>
      </div>
    </div>
  )
}

/**
 * Scroll-linked walkthrough: a pinned rail, copy and media on large screens; stacked sections
 * (with a jump list) on small screens and when the student prefers reduced motion.
 */
export function StickyStory({ label, steps, stepVh = 70, className }: StickyStoryProps) {
  const reduce = useReducedMotion()

  if (steps.length === 0) return null

  const stacked = (
    <>
      <JumpList label={label} steps={steps} />
      <StackedSteps steps={steps} />
    </>
  )

  if (reduce) {
    return <div className={className}>{stacked}</div>
  }

  return (
    <div className={className}>
      <div className="lg:hidden">{stacked}</div>
      <div className="hidden lg:block">
        <StickyTrack label={label} steps={steps} stepVh={stepVh} />
      </div>
    </div>
  )
}
