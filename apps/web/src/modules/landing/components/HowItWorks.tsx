import { Badge, Check, Flame, ProgressRing, Section, StickyStory, type StickyStoryStep } from '@artha/design-system'

import { howItWorksBeats } from '../data/story'
import { FrameShell } from './FrameShell'

function GoalFrame() {
  return (
    <FrameShell label="Onboarding">
      <p className="font-display text-xl font-bold">CA Intermediate · May 2027</p>
      <p className="mt-2 text-sm text-muted-foreground">2 h 30 min a day. Group I first.</p>
      <div className="mt-4 flex flex-wrap gap-2">
        <Badge variant="outline">ICAI</Badge>
        <Badge variant="outline">Intermediate</Badge>
        <Badge variant="outline">18 weeks</Badge>
      </div>
    </FrameShell>
  )
}

function TodayFrame() {
  return (
    <FrameShell label="Today">
      <ul className="space-y-2 text-sm">
        <li className="rounded-xl border bg-background px-4 py-3">Advanced Accounting: AS 19 — first read</li>
        <li className="rounded-xl border bg-background px-4 py-3">Taxation: GST ITC — 20 MCQs</li>
        <li className="rounded-xl border bg-background px-4 py-3 text-muted-foreground">
          Law: charges — revise tomorrow
        </li>
      </ul>
    </FrameShell>
  )
}

function ReadinessFrame() {
  return (
    <FrameShell label="Readiness">
      <div className="flex items-center gap-5">
        <ProgressRing value={68} size={96} strokeWidth={9} label="Overall readiness" />
        <div>
          <p className="font-display text-2xl font-extrabold">68%</p>
          <p className="text-sm text-muted-foreground">Chapters finished, not hours meant.</p>
          <Badge variant="highlight" className="mt-3">
            <Flame /> 12 day streak
          </Badge>
        </div>
      </div>
    </FrameShell>
  )
}

const frames = {
  goal: GoalFrame,
  today: TodayFrame,
  readiness: ReadinessFrame,
} as const

export function HowItWorks() {
  const steps: StickyStoryStep[] = howItWorksBeats.map((beat) => {
    const Frame = frames[beat.id]
    return {
      id: `how-${beat.id}`,
      rail: (
        <span className="flex items-baseline gap-2">
          <span className="font-display text-xs tabular-nums opacity-70">{beat.n}</span>
          <span>{beat.rail}</span>
        </span>
      ),
      content: (
        <div>
          <p className="mb-3 font-display text-5xl font-extrabold text-primary/20">{beat.n}</p>
          <h3 className="font-display text-2xl font-extrabold sm:text-3xl">{beat.title}</h3>
          <p className="prose-reading mt-4 text-base leading-relaxed text-muted-foreground sm:text-lg">{beat.body}</p>
          <ul className="mt-6 space-y-3">
            {beat.points.map((point) => (
              <li key={point} className="flex items-start gap-3 text-sm sm:text-base">
                <span className="mt-0.5 grid size-6 shrink-0 place-items-center rounded-full bg-accent/20 text-accent-foreground dark:text-accent">
                  <Check className="size-3.5" aria-hidden />
                </span>
                <span>{point}</span>
              </li>
            ))}
          </ul>
        </div>
      ),
      media: <Frame />,
    }
  })

  return (
    <Section
      id="how-it-works"
      align="left"
      eyebrow="How it works"
      title="From overwhelmed to on track"
      description="Three steps. The same goal feeds your coverage, your timer and your hours — so you are not running three apps that do not talk."
      className="bg-muted/40"
    >
      <StickyStory label="How ArthaCommerce works" steps={steps} stepVh={60} />
    </Section>
  )
}
