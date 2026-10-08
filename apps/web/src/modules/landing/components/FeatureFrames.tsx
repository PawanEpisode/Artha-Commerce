import { Badge, Check, cn, Flame, ProgressBar, ProgressRing } from '@artha/design-system'

import { FrameShell } from './FrameShell'

function Row({ done, label }: { done?: boolean; label: string }) {
  return (
    <li className="flex items-center gap-3 rounded-xl border bg-background px-3 py-2.5 text-sm">
      <span
        className={cn(
          'grid size-5 shrink-0 place-items-center rounded-full text-[11px]',
          done ? 'bg-accent text-accent-foreground' : 'border-2 border-border',
        )}
      >
        {done ? <Check className="size-3" aria-hidden /> : null}
      </span>
      <span className={done ? 'text-muted-foreground' : 'font-medium'}>{label}</span>
    </li>
  )
}

export function SyllabusFrame() {
  return (
    <FrameShell label="Coverage · CA Intermediate">
      <div className="mb-4 flex items-end justify-between gap-3">
        <div>
          <p className="font-display text-3xl font-extrabold tabular-nums">68%</p>
          <p className="text-xs text-muted-foreground">Advanced Accounting readiness</p>
        </div>
        <ProgressRing value={68} size={72} strokeWidth={8} label="Advanced Accounting readiness">
          <span className="sr-only">68%</span>
        </ProgressRing>
      </div>
      <ul className="space-y-2">
        <Row done label="AS 19 Leases — practised" />
        <Row done label="Company accounts — revised" />
        <Row label="Partnership — first read" />
      </ul>
    </FrameShell>
  )
}

export function FocusFrame() {
  return (
    <FrameShell label="Focus round">
      <div className="flex flex-col items-center py-2">
        <ProgressRing value={42} size={132} strokeWidth={10} label="Focus round remaining">
          <span className="text-center">
            <span className="block font-display text-3xl font-extrabold tabular-nums">14:32</span>
            <span className="text-[11px] text-muted-foreground">Classic · 25 min</span>
          </span>
        </ProgressRing>
        <p className="mt-4 text-sm text-muted-foreground">Ind AS 116 — first read</p>
      </div>
    </FrameShell>
  )
}

export function HoursFrame() {
  const days = [40, 70, 20, 90, 55, 0, 80]
  return (
    <FrameShell label="This week">
      <p className="font-display text-3xl font-extrabold tabular-nums">12 h 40 m</p>
      <p className="text-xs text-muted-foreground">Against a 14 hour goal</p>
      <ProgressBar value={90} label="Weekly hours against the 14 hour goal" className="mt-3" />
      <ol className="mt-5 flex items-end gap-2" aria-hidden>
        {days.map((h, i) => (
          <li key={i} className="flex flex-1 flex-col items-center gap-1">
            <span className="w-full rounded-md bg-primary/80" style={{ height: `${Math.max(8, h / 2)}px` }} />
            <span className="text-[10px] text-muted-foreground">{['M', 'T', 'W', 'T', 'F', 'S', 'S'][i]}</span>
          </li>
        ))}
      </ol>
      <p className="sr-only">Hours studied each day this week, Monday to Sunday.</p>
    </FrameShell>
  )
}

export function StreaksFrame() {
  return (
    <FrameShell label="Streak">
      <div className="mb-4 flex items-center justify-between">
        <Badge variant="highlight">
          <Flame /> 12 day streak
        </Badge>
        <p className="text-sm font-medium">4 papers touched</p>
      </div>
      <ul className="space-y-3">
        {[
          ['Direct Tax', 80],
          ['Law', 45],
          ['Audit', 20],
        ].map(([name, v]) => (
          <li key={String(name)}>
            <div className="mb-1 flex justify-between text-xs">
              <span>{name}</span>
              <span className="text-muted-foreground tabular-nums">{v}%</span>
            </div>
            <ProgressBar value={Number(v)} label={`${name} share of hours`} />
          </li>
        ))}
      </ul>
    </FrameShell>
  )
}

export function NotesFrame() {
  return (
    <FrameShell label="Notes · GST">
      <p className="font-display text-lg font-bold">Input tax credit</p>
      <p className="mt-2 text-sm leading-relaxed text-muted-foreground">
        Blocked credits under s.17(5) — motor vehicles, food, club memberships. File this under Indirect Tax, not a
        nameless doc.
      </p>
      <p className="mt-4 rounded-lg bg-secondary px-3 py-2 text-xs font-medium">Chapter · GST input tax credit</p>
    </FrameShell>
  )
}

export function PlannerFrame() {
  return (
    <FrameShell label="Plan · 18 weeks out">
      <ol className="space-y-3">
        {[
          ['Learn', '8 weeks · first read every chapter'],
          ['Revise', '6 weeks · second pass + RTPs'],
          ['Mock', '4 weeks · full papers under time'],
        ].map(([phase, detail]) => (
          <li key={phase} className="rounded-xl border bg-background px-4 py-3">
            <p className="text-sm font-semibold">{phase}</p>
            <p className="text-xs text-muted-foreground">{detail}</p>
          </li>
        ))}
      </ol>
    </FrameShell>
  )
}

export function MocksFrame() {
  return (
    <FrameShell label="Mock · Audit">
      <div className="flex items-center justify-between">
        <p className="font-display text-2xl font-extrabold tabular-nums">02:47:12</p>
        <Badge variant="outline">Exam mode</Badge>
      </div>
      <ProgressBar value={22} label="Mock paper time elapsed" className="mt-3" />
      <p className="mt-4 text-sm">Question 3 of 14 · 20 marks</p>
      <p className="mt-1 text-xs text-muted-foreground">SA 230 working papers — write, then review the misses.</p>
    </FrameShell>
  )
}

export function DoubtsFrame() {
  return (
    <FrameShell label="Doubt">
      <p className="rounded-xl bg-secondary px-3 py-2 text-sm">Why is a contingent liability not recognised?</p>
      <p className="mt-3 text-sm leading-relaxed text-muted-foreground">
        Because the outflow is not probable, or cannot be measured reliably. Disclose it, unless the chance is remote —
        then check the chapter note, not only this answer.
      </p>
    </FrameShell>
  )
}

export function CardsFrame() {
  return (
    <FrameShell label="Today’s queue · 12 cards">
      <div className="rounded-2xl border bg-background px-4 py-8 text-center">
        <p className="text-xs text-muted-foreground">Section</p>
        <p className="mt-2 font-display text-xl font-bold">s.185 — Loans to directors</p>
      </div>
      <p className="mt-3 text-center text-xs text-muted-foreground">Show answer when you have it, not before.</p>
    </FrameShell>
  )
}

export function PapersFrame() {
  return (
    <FrameShell label="Past attempts">
      <ul className="space-y-2">
        {[
          ['May 2024 · Adv. Accounts', 'Q1, Q4 — company accounts'],
          ['Nov 2023 · Law', 'Q2 — charges'],
          ['MTP 1 · Audit', 'Not started'],
        ].map(([title, detail]) => (
          <li key={title} className="rounded-xl border bg-background px-4 py-3">
            <p className="text-sm font-medium">{title}</p>
            <p className="text-xs text-muted-foreground">{detail}</p>
          </li>
        ))}
      </ul>
    </FrameShell>
  )
}

export function AmendmentsFrame() {
  return (
    <FrameShell label="This sitting">
      <p className="text-sm font-semibold">Finance Act changes — mapped to Direct Tax</p>
      <p className="mt-2 text-sm text-muted-foreground">
        Applicable for your attempt. Open the chapter note before you revise last year’s summary.
      </p>
      <Badge variant="outline" className="mt-4">
        Applies · May 2027
      </Badge>
    </FrameShell>
  )
}

const frames = {
  'syllabus-tracker': SyllabusFrame,
  'pomodoro-focus-timer': FocusFrame,
  'time-tracker': HoursFrame,
  'streaks-analytics': StreaksFrame,
  'smart-notes': NotesFrame,
  'study-planner': PlannerFrame,
  'mock-tests': MocksFrame,
  'ai-doubt-solver': DoubtsFrame,
  flashcards: CardsFrame,
  'past-papers': PapersFrame,
  'amendment-updates': AmendmentsFrame,
} as const

export function FeatureFrame({ slug }: { slug: string }) {
  const Frame = frames[slug as keyof typeof frames]
  if (!Frame) return null
  return <Frame />
}
