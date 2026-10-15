import { toast } from '@artha/design-system'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useRef, useState } from 'react'

import { coverageKeys, updateEnrollment, useEnrollments } from '~/modules/coverage'
import { fetchTerms } from '~/modules/syllabus'

import { examBucket, trackToday } from '../lib/analytics'
import { errorMessage, rebuildToday } from '../lib/api'
import { dismissExamCard, examCardDismissed, shouldOfferExamCard, type TermOption, upcomingTerms } from '../lib/exam'
import { todayKeys } from '../lib/keys'
import type { OpenResult, Plan } from '../lib/types'

/**
 * The "Pick your attempt" card (PRD 7.3). Offered when the plan has no exam date and the card was not dismissed on this device.
 * Choosing a term or typing a date saves it on the enrolment and rebuilds today's plan once ("Plan updated for your attempt").
 */
export function useExamDate(plan: Plan, enabled: boolean) {
  const qc = useQueryClient()
  const enrollments = useEnrollments()
  const active = enrollments.data?.find((e) => e.status === 'active') ?? null
  const terms = useQuery({
    queryKey: ['syllabus', 'terms', active?.course.code, active?.level.code],
    queryFn: () => fetchTerms(active?.course.code, active?.level.code),
    enabled: enabled && active !== null,
    staleTime: 10 * 60_000,
  })
  const [dismissed, setDismissed] = useState(examCardDismissed)
  const [error, setError] = useState<string | null>(null)
  const offer = enabled && active !== null && shouldOfferExamCard(plan.days_to_exam, dismissed)

  const shown = useRef(false)
  useEffect(() => {
    if (offer && !shown.current) {
      shown.current = true
      trackToday('today_exam_date_prompted', { days_to_exam_bucket: examBucket(plan.days_to_exam) })
    }
  }, [offer, plan.days_to_exam])

  const save = useMutation({
    mutationFn: async (input: {
      patch: { target_term?: string | null; exam_date?: string | null }
      action: 'chip' | 'custom'
    }) => {
      if (!active) throw new Error('no enrolment')
      await updateEnrollment(active.id, input.patch)
      await qc.invalidateQueries({ queryKey: coverageKeys.all })
      return rebuildToday('exam_date')
    },
    onSuccess: (rebuilt, input) => {
      setError(null)
      if (rebuilt) qc.setQueryData<OpenResult>(todayKeys.plan, rebuilt)
      else void qc.invalidateQueries({ queryKey: todayKeys.plan })
      trackToday('today_exam_date_set', {
        action: input.action,
        days_to_exam_bucket: examBucket(rebuilt?.days_to_exam ?? null),
      })
      toast.success('Plan updated for your attempt')
    },
    onError: (e) => setError(errorMessage(e, 'We could not save that. Please try again.')),
  })

  return {
    offer,
    terms: upcomingTerms((terms.data ?? []) as TermOption[], plan.date),
    pending: save.isPending,
    error,
    pickTerm: (term: TermOption) => save.mutate({ patch: { target_term: term.id }, action: 'chip' }),
    customDate: (date: string) => save.mutate({ patch: { exam_date: date }, action: 'custom' }),
    dismiss: () => {
      dismissExamCard()
      setDismissed(true)
      trackToday('today_exam_date_prompted', {
        action: 'dismissed',
        days_to_exam_bucket: examBucket(plan.days_to_exam),
      })
    },
  }
}
