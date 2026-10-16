import { Alert, Button, Sparkles, toast } from '@artha/design-system'
import { useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'

import { useAnswerSuggestion, useBudgetSuggestion, useSendFeedback } from '../hooks/usePlanner'
import { usePlannerFlag } from '../hooks/usePlannerFlag'
import { trackToday } from '../lib/analytics'
import { errorCode, errorDetails, errorMessage } from '../lib/api'
import { todayKeys } from '../lib/keys'
import { addBonus } from '../lib/planner-api'
import type { FeedbackRating } from '../lib/planner-types'
import { formatMinutes } from '../lib/time'
import type { Plan } from '../lib/types'

const RATINGS: { value: FeedbackRating; label: string }[] = [
  { value: 'too_much', label: 'Too much' },
  { value: 'just_right', label: 'Just right' },
  { value: 'too_little', label: 'Too little' },
]

const memoryKey = (date: string) => `today:feedback:${date}`

function remembered(date: string): FeedbackRating | null {
  try {
    const v = window.localStorage.getItem(memoryKey(date))
    return RATINGS.some((r) => r.value === v) ? (v as FeedbackRating) : null
  } catch {
    return null // private window or blocked storage: the card just shows again
  }
}

function remember(date: string, rating: FeedbackRating) {
  try {
    window.localStorage.setItem(memoryKey(date), rating)
  } catch {
    /* ignore */
  }
}

/** "How was today's plan?" One tap after the day closes (FR-F13-37). */
function FeedbackCard({ plan }: { plan: Plan }) {
  const send = useSendFeedback()
  const [given, setGiven] = useState<FeedbackRating | null>(() => remembered(plan.date))
  if (given) {
    return (
      <p role="status" className="text-center text-[13px] text-muted-foreground">
        Thanks. We will use this to size your days.
      </p>
    )
  }
  const pick = (rating: FeedbackRating) =>
    send.mutate(
      { rating, date: plan.date },
      {
        onSuccess: () => {
          remember(plan.date, rating)
          setGiven(rating)
          trackToday('today_feedback_given', { rating })
        },
        onError: (error) => toast.error(errorMessage(error)),
      },
    )
  return (
    <section
      aria-labelledby="feedback-heading"
      className="space-y-2 rounded-lg border border-border bg-card p-3 shadow-soft"
    >
      <h2 id="feedback-heading" className="text-sm font-semibold">
        How was today's plan?
      </h2>
      <div role="group" aria-label="Rate today's plan" className="flex flex-wrap gap-2">
        {RATINGS.map((r) => (
          <Button key={r.value} variant="outline" size="sm" disabled={send.isPending} onClick={() => pick(r.value)}>
            {r.label}
          </Button>
        ))}
      </div>
    </section>
  )
}

/** Three days of "too much" (or "too little") in a row: one tap to change the daily minutes, or to keep them. */
function SuggestionCard() {
  const suggestion = useBudgetSuggestion(true).data?.suggestion ?? null
  const answer = useAnswerSuggestion()
  if (!suggestion) return null
  const fewer = suggestion.direction === 'too_much'
  const respond = (accept: boolean) =>
    answer.mutate(accept, {
      onSuccess: () =>
        toast.success(
          accept ? `Your days are now about ${formatMinutes(suggestion.minutes)}` : 'We will keep your minutes',
        ),
      onError: (error) => toast.error(errorMessage(error)),
    })
  return (
    <Alert variant="info">
      <div className="space-y-2">
        <p>
          {fewer ? 'Three days in a row felt like too much.' : 'Three days in a row felt like too little.'} Try{' '}
          <strong>{formatMinutes(suggestion.minutes)}</strong> a day instead of {formatMinutes(suggestion.current)}?
        </p>
        <div className="flex flex-wrap gap-2">
          <Button size="sm" disabled={answer.isPending} onClick={() => respond(true)}>
            Use {formatMinutes(suggestion.minutes)}
          </Button>
          <Button size="sm" variant="outline" disabled={answer.isPending} onClick={() => respond(false)}>
            Keep {formatMinutes(suggestion.current)}
          </Button>
        </div>
      </div>
    </Alert>
  )
}

/** "Do a little more" after a completed day: up to 3 extra tasks within 20 minutes that never count (FR-F13-36). */
function BonusCard({ plan }: { plan: Plan }) {
  const qc = useQueryClient()
  const [busy, setBusy] = useState(false)
  if (plan.tasks.some((t) => t.is_bonus)) return null // already used today
  const run = async () => {
    setBusy(true)
    try {
      const res = await addBonus()
      toast.success(
        `Added ${res.bonus.added} bonus ${res.bonus.added === 1 ? 'task' : 'tasks'}. They never count against your day.`,
      )
      await qc.invalidateQueries({ queryKey: todayKeys.plan })
    } catch (error) {
      const reason = errorCode(error) === 'bonus_not_available' ? errorDetails(error).reason : null
      toast.info(
        reason === 'nothing_to_offer'
          ? 'Nothing extra to suggest right now. Enjoy the break.'
          : reason === 'already_used'
            ? 'You already added a bonus round today.'
            : errorMessage(error),
      )
      if (reason) await qc.invalidateQueries({ queryKey: todayKeys.plan })
    } finally {
      setBusy(false)
    }
  }
  return (
    <section
      aria-label="Bonus round"
      className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-border bg-card p-3 shadow-soft"
    >
      <p className="text-[13px] text-muted-foreground">Still going? A few extra minutes, no pressure.</p>
      <Button variant="outline" size="sm" disabled={busy} onClick={() => void run()}>
        <Sparkles aria-hidden /> {busy ? 'Adding' : 'Do a little more'}
      </Button>
    </section>
  )
}

/**
 * What the Today screen adds once the day has closed (R2, behind `today_planner`): the one-tap feedback, a standing budget
 * suggestion and, after a completed day, the bonus round. Renders nothing for a past day, a day still in progress or a student
 * without the flag.
 */
export function DayExtras({ plan, readOnly }: { plan: Plan; readOnly: boolean }) {
  const enabled = usePlannerFlag()
  if (!enabled || readOnly || plan.closing === null) return null
  return (
    <div className="space-y-3">
      <SuggestionCard />
      <FeedbackCard plan={plan} />
      {plan.closing === 'celebrate' ? <BonusCard plan={plan} /> : null}
    </div>
  )
}
