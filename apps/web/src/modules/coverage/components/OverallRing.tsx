import { Badge, Card, Label, ProgressRing, Switch } from '@artha/design-system'
import type { ReactNode } from 'react'

import { progressSentence } from '../lib/progress'
import type { Enrollment } from '../lib/types'

interface Props {
  enrollment: Enrollment
  percent: number
  chaptersDone: number
  chaptersStarted: number
  chaptersTotal: number
  weighted: boolean
  onWeightedChange: (weighted: boolean) => void
  /** The "How is this calculated?" control. */
  calculation: ReactNode
}

/** Hero of the syllabus map: overall ring, enrolment context and the simple/weighted toggle (FR-23). */
export function OverallRing({
  enrollment,
  percent,
  chaptersDone,
  chaptersStarted,
  chaptersTotal,
  weighted,
  onWeightedChange,
  calculation,
}: Props) {
  return (
    <Card className="flex flex-col items-center gap-5 p-6 text-center sm:flex-row sm:text-left">
      <ProgressRing value={percent} label="Average progress across chapters" size={140} strokeWidth={12} />
      <div className="min-w-0 flex-1 space-y-3">
        <div>
          <h1 className="font-display text-2xl font-extrabold">
            {enrollment.course.name} {enrollment.level.name}
          </h1>
          <p className="mt-1 flex flex-wrap items-center justify-center gap-2 text-sm text-muted-foreground sm:justify-start">
            {enrollment.target_term ? <span>{enrollment.target_term.name}</span> : null}
            {enrollment.days_remaining !== null ? (
              <Badge variant="highlight">{enrollment.days_remaining} days to go</Badge>
            ) : null}
          </p>
        </div>
        <p className="text-sm text-muted-foreground">
          {progressSentence({ chaptersDone, chaptersStarted, chaptersTotal })}
        </p>
        <div className="flex flex-wrap items-center justify-center gap-x-4 gap-y-1 sm:justify-start">
          <div className="flex items-center gap-2">
            <Switch id="weighted-view" checked={weighted} onCheckedChange={onWeightedChange} />
            <Label htmlFor="weighted-view">Weight by marks</Label>
          </div>
          {calculation}
        </div>
      </div>
    </Card>
  )
}
