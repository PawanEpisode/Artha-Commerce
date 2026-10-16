import { ArrowRight, Button, Card, ProgressRing } from '@artha/design-system'
import { Link } from '@tanstack/react-router'
import { useEffect, useState } from 'react'

import { useFeatureFlag } from '~/modules/observability'

interface Props {
  levelName: string
  percent: number
  /** The paper to start with: lowest coverage. */
  startWith: { name: string; notStarted: number } | null
}

/** The aha moment: the ring animates from 0 to the starting point and says what is left. */
export function CatchupResult({ levelName, percent, startWith }: Props) {
  const [shown, setShown] = useState(0)
  const todayOn = useFeatureFlag('today_plan', { strict: true })
  useEffect(() => {
    const id = requestAnimationFrame(() => setShown(percent))
    return () => cancelAnimationFrame(id)
  }, [percent])
  return (
    <Card className="flex flex-col items-center gap-4 p-6 text-center">
      <ProgressRing value={shown} label="Coverage so far" size={160} strokeWidth={14} />
      <div role="status" className="space-y-2">
        <p className="text-base font-semibold">
          You have already covered {percent}% of {levelName}. {100 - percent}% to go.
        </p>
        {startWith ? (
          <p className="text-muted-foreground">
            Start with {startWith.name}
            {startWith.notStarted > 0
              ? `: ${startWith.notStarted} chapter${startWith.notStarted === 1 ? '' : 's'} not started.`
              : '.'}
          </p>
        ) : null}
      </div>
      {todayOn ? (
        <div className="flex flex-col items-center gap-3">
          <Button asChild>
            <Link to="/app/today" search={{ from: 'onboarding' }}>
              See today's plan <ArrowRight />
            </Link>
          </Button>
          <Button variant="ghost" asChild>
            <Link to="/app/syllabus">Open my syllabus map</Link>
          </Button>
        </div>
      ) : (
        <Button asChild>
          <Link to="/app/syllabus">
            Open my syllabus map <ArrowRight />
          </Link>
        </Button>
      )}
    </Card>
  )
}
