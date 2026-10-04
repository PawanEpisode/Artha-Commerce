import { motion } from 'motion/react'
import { Card } from '~/components/ui/card'
import { Tabs, TabsList, TabsTrigger } from '~/components/ui/tabs'
import { cn } from '~/lib/utils'
import { courses, type Course, type CourseSlug, type Level } from '~/modules/catalog'
import type { PlanResult } from '../lib/plan'

interface Props {
  course: Course
  level: Level
  levelIndex: number
  plan: PlanResult
  months: number
  hoursPerDay: number
  onCourse: (slug: CourseSlug) => void
  onLevel: (index: number) => void
  onMonths: (n: number) => void
  onHours: (n: number) => void
}

const phaseTone = { learn: 'bg-primary', revise: 'bg-accent', mock: 'bg-highlight' } as const

function Slider({ id, label, value, min, max, unit, onChange }: { id: string; label: string; value: number; min: number; max: number; unit: string; onChange: (n: number) => void }) {
  return (
    <div>
      <div className="mb-2 flex items-baseline justify-between text-sm">
        <label htmlFor={id} className="font-medium">
          {label}
        </label>
        <span className="font-display text-lg font-bold tabular-nums">
          {value} <span className="text-sm font-medium text-muted-foreground">{unit}</span>
        </span>
      </div>
      <input
        id={id}
        type="range"
        min={min}
        max={max}
        value={value}
        onChange={(e) => onChange(Number(e.target.value))}
        className="h-2 w-full cursor-pointer accent-primary"
      />
    </div>
  )
}

/** Presentational. Receives everything via props from usePlannerPreview. */
export function PlannerPreviewView({ course, level, levelIndex, plan, months, hoursPerDay, onCourse, onLevel, onMonths, onHours }: Props) {
  const maxSubject = Math.max(...plan.perSubject.map((s) => s.hours), 1)
  return (
    <Card className="grid gap-0 overflow-hidden shadow-lift lg:grid-cols-[minmax(0,5fr)_minmax(0,7fr)]">
      <div className="space-y-6 border-b p-6 sm:p-8 lg:border-b-0 lg:border-r">
        <Tabs value={course.slug} onValueChange={(v) => onCourse(v as CourseSlug)}>
          <TabsList aria-label="Course">
            {courses.map((c) => (
              <TabsTrigger key={c.slug} value={c.slug}>
                {c.name}
              </TabsTrigger>
            ))}
          </TabsList>
        </Tabs>
        <div role="group" aria-label="Level" className="flex flex-wrap gap-2">
          {course.levels.map((l, i) => (
            <button
              key={l.slug}
              type="button"
              aria-pressed={i === levelIndex}
              onClick={() => onLevel(i)}
              className={cn(
                'rounded-full border px-4 py-1.5 text-sm font-semibold transition-colors',
                i === levelIndex ? 'border-primary bg-primary text-primary-foreground' : 'hover:bg-muted',
              )}
            >
              {l.name}
            </button>
          ))}
        </div>
        <Slider id="months" label="Months until your exam" value={months} min={1} max={12} unit={months === 1 ? 'month' : 'months'} onChange={onMonths} />
        <Slider id="hours" label="Study hours per day" value={hoursPerDay} min={1} max={10} unit="hrs" onChange={onHours} />
      </div>

      <div className="space-y-6 bg-muted/40 p-6 sm:p-8" aria-live="polite">
        <div className="flex items-end justify-between gap-4">
          <div>
            <p className="text-sm text-muted-foreground">Your {course.name} {level.name} plan</p>
            <p className="font-display text-5xl font-extrabold tabular-nums">
              {plan.totalHours.toLocaleString('en-IN')}
              <span className="ml-1 text-lg font-semibold text-muted-foreground">study hours</span>
            </p>
          </div>
          <p className="text-right text-sm text-muted-foreground">{plan.studyDays} study days</p>
        </div>

        <div>
          <div className="flex h-3 overflow-hidden rounded-full bg-border">
            {plan.phases.map((p) => (
              <motion.div key={p.key} className={phaseTone[p.key]} animate={{ width: `${p.share * 100}%` }} transition={{ duration: 0.5 }} />
            ))}
          </div>
          <ul className="mt-3 grid grid-cols-3 gap-2 text-xs">
            {plan.phases.map((p) => (
              <li key={p.key} className="flex items-center gap-2">
                <span className={cn('size-2.5 rounded-full', phaseTone[p.key])} />
                <span className="text-muted-foreground">
                  {p.label} <strong className="text-foreground">{p.hours}h</strong>
                </span>
              </li>
            ))}
          </ul>
        </div>

        <ul className="space-y-3">
          {plan.perSubject.map((s) => (
            <li key={s.name}>
              <div className="mb-1 flex justify-between gap-3 text-sm">
                <span className="truncate font-medium">{s.name}</span>
                <span className="tabular-nums text-muted-foreground">{s.hours}h</span>
              </div>
              <div className="h-1.5 overflow-hidden rounded-full bg-border">
                <motion.div className="h-full rounded-full bg-primary/70" animate={{ width: `${(s.hours / maxSubject) * 100}%` }} transition={{ duration: 0.5 }} />
              </div>
            </li>
          ))}
        </ul>
        <p className="text-xs text-muted-foreground">Illustrative split. Your real plan adapts to your pace and weak areas.</p>
      </div>
    </Card>
  )
}
