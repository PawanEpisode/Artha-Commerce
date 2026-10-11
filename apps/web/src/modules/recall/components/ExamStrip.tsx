import { ButtonLink, CalendarDays, Zap } from '@artha/design-system'
import { Link } from '@tanstack/react-router'

import { countdown, pacingMessage } from '../lib/examText'
import { plural } from '../lib/format'
import type { ExamBlock } from '../lib/schemas'

/**
 * The exam on the Revision hub: the countdown, the quick revision invitation (from 45 days out, when the plan has enough
 * cards), the cram button in the last 24 hours and the pacing note. Props only; the links carry the state in the URL.
 */
export function ExamStrip({ exam }: { exam: ExamBlock }) {
  const quick = exam.quick
  return (
    <section
      aria-labelledby="exam-heading"
      className="space-y-3 rounded-2xl border border-border bg-card p-5 shadow-soft"
    >
      <div className="flex items-center gap-2">
        <CalendarDays className="size-5 text-primary" aria-hidden />
        <h2 id="exam-heading" className="font-display text-lg font-bold">
          {countdown(exam.days_to_exam, exam.cram_open)}
        </h2>
      </div>
      {exam.cram_open ? (
        <div className="space-y-2">
          <p className="text-sm text-muted-foreground">
            One last look at the cards that matter most. It does not change your schedule.
          </p>
          <ButtonLink asChild>
            <Link to="/app/recall/review" search={{ source: 'cram' }}>
              <Zap className="size-4" aria-hidden />
              Last-day cram
            </Link>
          </ButtonLink>
        </div>
      ) : null}
      {quick && !quick.too_few ? (
        <div className="space-y-2">
          <p className="text-sm text-muted-foreground">
            {plural(quick.selected, 'card')} could fade before the exam. A quick plan is about {quick.per_day} a day,{' '}
            {quick.minutes_per_day} min.
          </p>
          <ButtonLink variant="outline" asChild>
            <Link to="/app/recall/quick" search={{}}>
              Plan quick revision
            </Link>
          </ButtonLink>
        </div>
      ) : null}
      {exam.pacing && exam.pacing.unseen > 0 ? (
        <p className="text-sm text-muted-foreground" data-testid="pacing">
          {pacingMessage(exam.pacing)}
        </p>
      ) : null}
    </section>
  )
}
