import { Badge, Label, PageHeader, ProgressBar, StatTile, Switch } from '@artha/design-system'
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
  /** The "Revise what is due" link, when something is due. */
  dueAction?: ReactNode
}

/** Head of the syllabus map: the course and level, the weighting switch, and one row of headline numbers (FR-23). */
export function OverallRing({
  enrollment,
  percent,
  chaptersDone,
  chaptersStarted,
  chaptersTotal,
  weighted,
  onWeightedChange,
  calculation,
  dueAction,
}: Props) {
  const started = Math.max(chaptersStarted, chaptersDone)
  return (
    <>
      <PageHeader
        title={`${enrollment.course.name} ${enrollment.level.name}`}
        description={
          enrollment.target_term || enrollment.days_remaining !== null ? (
            <span className="flex flex-wrap items-center gap-2">
              {enrollment.target_term ? <span>{enrollment.target_term.name}</span> : null}
              {enrollment.days_remaining !== null ? (
                <Badge variant="highlight">{enrollment.days_remaining} days to go</Badge>
              ) : null}
            </span>
          ) : undefined
        }
        actions={
          <>
            <div className="flex items-center gap-2">
              <Switch id="weighted-view" checked={weighted} onCheckedChange={onWeightedChange} />
              <Label htmlFor="weighted-view">Weight by marks</Label>
            </div>
            {calculation}
            {dueAction}
          </>
        }
      />
      <div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:max-w-4xl">
        <StatTile
          label="Overall progress"
          value={`${percent}%`}
          hint={<ProgressBar size="sm" value={percent} label="Average progress across chapters" className="mt-1.5" />}
          className="col-span-2 md:col-span-1"
        />
        <StatTile label="Chapters finished" value={`${chaptersDone} of ${chaptersTotal}`} />
        <StatTile label="Chapters started" value={started} />
      </div>
      <p className="text-xs text-muted-foreground">
        {progressSentence({ chaptersDone, chaptersStarted, chaptersTotal })}
      </p>
    </>
  )
}
