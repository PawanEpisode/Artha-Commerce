import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { errorCode, isFeatureDisabled } from '../lib/api'
import { todayKeys } from '../lib/keys'
import {
  answerBudgetSuggestion,
  chooseReplanOption,
  createStudyPlan,
  getBudgetSuggestion,
  getStudyPlan,
  replanNow,
  sendFeedback,
} from '../lib/planner-api'
import type { BudgetSuggestionResponse, FeedbackRating, OptionChoice, StudyPlan } from '../lib/planner-types'

/** The study plan. A 404 `study_plan_not_found` is an answer ("make one"), not a failure, so it is not retried. */
export function useStudyPlan(enabled = true) {
  return useQuery({
    queryKey: todayKeys.studyPlan,
    queryFn: getStudyPlan,
    enabled,
    staleTime: 60_000,
    refetchOnWindowFocus: true,
    retry: (count, error) => !isFeatureDisabled(error) && errorCode(error) !== 'study_plan_not_found' && count < 2,
  })
}

export const hasNoStudyPlan = (error: unknown) => errorCode(error) === 'study_plan_not_found'

/** Today's suggestions come from the plan (the planner provider), so a changed plan refreshes them. */
function useAfterPlanChange() {
  const qc = useQueryClient()
  return (plan: StudyPlan) => {
    qc.setQueryData<StudyPlan>(todayKeys.studyPlan, plan)
    void qc.invalidateQueries({ queryKey: todayKeys.plan })
  }
}

export function useCreateStudyPlan() {
  const done = useAfterPlanChange()
  return useMutation({ mutationFn: (minutes?: number) => createStudyPlan(minutes), onSuccess: done })
}

export function useReplan() {
  const done = useAfterPlanChange()
  return useMutation({ mutationFn: replanNow, onSuccess: done })
}

export function useChooseOption() {
  const done = useAfterPlanChange()
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ eventId, option }: { eventId: string; option: OptionChoice }) => chooseReplanOption(eventId, option),
    onSuccess: (plan) => {
      done(plan)
      void qc.invalidateQueries({ queryKey: todayKeys.settings }) // a chosen exam date or minutes shows in the settings too
    },
  })
}

// ---- the Today screen's day extras -----------------------------------------------------------------------------------------

export function useBudgetSuggestion(enabled: boolean) {
  return useQuery({
    queryKey: todayKeys.budgetSuggestion,
    queryFn: getBudgetSuggestion,
    enabled,
    staleTime: 60_000,
    retry: false,
  })
}

export function useSendFeedback() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ rating, date }: { rating: FeedbackRating; date?: string }) => sendFeedback(rating, date),
    onSuccess: (res) =>
      qc.setQueryData<BudgetSuggestionResponse>(todayKeys.budgetSuggestion, {
        version: res.version,
        server_time: res.server_time,
        suggestion: res.suggestion,
      }),
  })
}

export function useAnswerSuggestion() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (accept: boolean) => answerBudgetSuggestion(accept),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: todayKeys.budgetSuggestion })
      void qc.invalidateQueries({ queryKey: todayKeys.settings })
    },
  })
}
