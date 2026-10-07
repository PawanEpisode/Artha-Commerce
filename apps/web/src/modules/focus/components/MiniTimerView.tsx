import {
  ArrowLeft,
  Button,
  Check,
  cn,
  Coffee,
  type LucideIcon,
  Maximize2,
  Minimize2,
  Pause,
  Play,
  SkipForward,
  Square,
  Timer,
  X,
} from '@artha/design-system'
import type { ReactNode } from 'react'

import type { PopoutControl, PopoutControlId, PopoutIcon, PopoutView } from '../lib/popout'
import { TimerRing } from './TimerRing'

export type MiniVariant = 'corner' | 'pill' | 'card'

interface Props {
  /** `corner` is the fixed timer on every page; `pill` and `card` fill the floating window. */
  variant: MiniVariant
  view: PopoutView
  /** The controls to draw, already narrowed to this size by the container. The corner only uses Pause and Resume. */
  controls: readonly PopoutControl[]
  busy: boolean
  onControl: (id: PopoutControlId) => void
  /** Subject and chapter, shown as the card's title. */
  context?: string
  /** A question above the controls ("End this round early?"), shown in the card. */
  prompt?: string
  /** Polite live-region text for screen readers (the floating window has its own). */
  announcement?: string
  /** Corner only: the link wrapping the clock, so the container owns routing. */
  renderLink?: (children: ReactNode) => ReactNode
  /** Corner only: extra action after the controls (Pop out, Bring back). */
  action?: ReactNode
  /** Window only: switches between the pill and the card. */
  onToggleSize?: () => void
}

const ICONS: Record<Exclude<PopoutIcon, null>, LucideIcon> = {
  pause: Pause,
  play: Play,
  skip: SkipForward,
  stop: Square,
  coffee: Coffee,
  back: ArrowLeft,
  check: Check,
  close: X,
}

/** A pill or card holds at most three buttons in 296 px, so they drop their icons and keep the words. */
function ControlButton({
  control: c,
  lead,
  stretch,
  large,
  busy,
  onControl,
}: {
  control: PopoutControl
  lead: boolean
  stretch: boolean
  large: boolean
  busy: boolean
  onControl: (id: PopoutControlId) => void
}) {
  const Icon = c.icon ? ICONS[c.icon] : null
  const common = { onClick: () => onControl(c.id), disabled: busy || c.disabled }
  if (c.iconOnly)
    return (
      <Button size="icon" variant="outline" aria-label={c.label} {...common}>
        {Icon ? <Icon aria-hidden /> : null}
      </Button>
    )
  return (
    <Button
      size={large ? 'lg' : 'default'}
      variant={c.primary ? 'default' : 'outline'}
      className={cn('px-3', stretch && 'min-w-0 flex-1', large && 'w-full')}
      {...common}
    >
      {Icon && lead ? <Icon aria-hidden /> : null}
      {c.label}
    </Button>
  )
}

/** The corner timer: the clock as a link to its page, Pause or Resume, and room for one more action. */
function Corner({ view, controls, busy, onControl, renderLink, action }: Props) {
  const Icon = view.phase === 'short_break' || view.phase === 'long_break' ? Coffee : Timer
  const toggle = controls.find((c) => c.id === 'pause' || c.id === 'resume')
  return (
    <div
      role="region"
      aria-label={`Running ${view.label.toLowerCase()}`}
      className="fixed right-4 bottom-4 z-40 flex items-center gap-2 rounded-2xl border border-border bg-popover p-2 pl-4 shadow-(--shadow-lift)"
    >
      <Icon className="size-4 text-primary" aria-hidden />
      {(renderLink ?? ((children: ReactNode) => children))(
        <>
          <span className="sr-only">
            Open the {view.label.toLowerCase()}. {view.spoken}.{' '}
          </span>
          <span aria-hidden className="font-display font-bold tabular-nums">
            {view.clock}
          </span>
        </>,
      )}
      {toggle ? (
        <Button
          size="icon"
          variant={toggle.id === 'resume' ? 'default' : 'outline'}
          aria-label={`${toggle.label} ${view.label.toLowerCase()}`}
          onClick={() => onControl(toggle.id)}
          disabled={busy || toggle.disabled}
        >
          {toggle.id === 'resume' ? <Play aria-hidden /> : <Pause aria-hidden />}
        </Button>
      ) : null}
      {action}
    </div>
  )
}

/** What the round is called in the ring: "Paused" and "Extra focus" say more than the phase does. */
const ringLabel = (v: PopoutView) =>
  v.paused ? 'Paused' : v.kind === 'overtime' ? 'Extra focus' : v.phase === 'focus' ? 'Focus' : v.label

/**
 * The timer in all three places it lives: the corner of every page, and the pill and the card of the floating window
 * (X-01 W4.2). One view of the timer, drawn three ways. The window layouts follow the window's own width through
 * container queries, so a window the browser makes bigger or smaller still reads well. Every button is at least 40 px.
 */
export function MiniTimerView(p: Props) {
  if (p.variant === 'corner') return <Corner {...p} />
  const { view, controls, variant } = p
  const card = variant === 'card'
  const HeaderIcon = view.phase === 'short_break' || view.phase === 'long_break' ? Coffee : Timer
  const wordy = view.kind === 'away' || view.kind === 'waiting' || view.kind === 'idle'
  // Three buttons share 296 px; with two or fewer there is room for the icons.
  const lead = controls.length <= 2
  const row = (stretch: boolean, large = false) =>
    controls.map((c) => (
      <ControlButton
        key={c.id}
        control={c}
        lead={lead}
        stretch={stretch}
        large={large}
        busy={p.busy}
        onControl={p.onControl}
      />
    ))
  return (
    <div className="@container h-dvh w-full">
      <section
        aria-label="Artha timer"
        className={cn(
          'flex h-full min-h-0 flex-col gap-1.5 overflow-y-auto p-3 pt-2 font-sans',
          view.ended ? 'bg-success-bg text-success-fg' : 'bg-background text-foreground',
        )}
      >
        <p role="status" aria-live="polite" className="sr-only">
          {p.announcement}
        </p>
        <header className="flex min-h-10 items-center gap-2">
          <HeaderIcon className="size-4 shrink-0" aria-hidden />
          <p className="min-w-0 flex-1 truncate text-sm font-semibold">
            {card ? (p.context ?? view.label) : [view.label, view.caption].filter(Boolean).join(' · ')}
          </p>
          {p.onToggleSize ? (
            <Button
              size="icon"
              variant="ghost"
              aria-label={card ? 'Switch to the compact size' : 'Switch to the card size'}
              onClick={p.onToggleSize}
            >
              {card ? <Minimize2 aria-hidden /> : <Maximize2 aria-hidden />}
            </Button>
          ) : null}
        </header>

        {card ? (
          <>
            <div className="flex min-h-0 flex-1 flex-col items-center justify-center gap-1 text-center">
              {view.ring ? (
                <TimerRing
                  compact
                  ended={view.ended}
                  phase={view.phase === 'stopwatch' ? null : view.phase}
                  status={view.paused ? 'paused' : view.ended ? null : 'running'}
                  remainingSeconds={0}
                  percent={view.percent}
                  caption={view.caption}
                  clock={view.clock}
                  label={ringLabel(view)}
                  spoken={view.spoken}
                />
              ) : (
                <>
                  <p
                    role="timer"
                    aria-label={view.spoken}
                    className={cn('font-display font-extrabold', wordy ? 'text-2xl' : 'text-5xl tabular-nums')}
                  >
                    <span aria-hidden>{view.clock}</span>
                  </p>
                  <p className={cn('text-sm', !view.ended && 'text-muted-foreground')}>
                    {view.message ?? view.caption}
                  </p>
                </>
              )}
            </div>
            {p.prompt ? <p className="text-center text-sm font-semibold">{p.prompt}</p> : null}
            <div className="flex gap-2">{row(controls.length > 1, controls.length === 1)}</div>
          </>
        ) : (
          <div className="flex min-h-0 flex-1 items-center justify-between gap-2">
            <p
              role="timer"
              aria-label={view.spoken}
              className={cn(
                'min-w-0 font-display font-extrabold',
                wordy ? 'text-2xl leading-tight @sm:text-3xl' : 'truncate text-4xl tabular-nums @sm:text-5xl',
              )}
            >
              <span aria-hidden>{view.clock}</span>
            </p>
            <div className="flex shrink-0 items-center gap-2">{row(false)}</div>
          </div>
        )}
      </section>
    </div>
  )
}
