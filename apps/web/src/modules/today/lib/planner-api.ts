import { api } from '~/lib/api'

import type {
  BudgetSuggestionResponse,
  FeedbackRating,
  FeedbackResponse,
  OptionChoice,
  ReplanEvent,
  StudyPlan,
  StudyPlanCreated,
  StudyPlanReplanned,
} from './planner-types'
import type { Plan } from './types'

const post = <T>(path: string, body: unknown = {}) => api<T>(path, { method: 'POST', body: JSON.stringify(body) })

/** The study plan, read only. 404 `study_plan_not_found` means the student has none yet. */
export const getStudyPlan = () => api<StudyPlan>('/today/planner/')

/** Makes the plan (201) or returns it (200). With `dailyMinutes` on an existing plan it re-plans for that time. */
export const createStudyPlan = (dailyMinutes?: number) =>
  post<StudyPlanCreated>('/today/planner/', dailyMinutes === undefined ? {} : { daily_minutes: dailyMinutes })

/** The student's own "Re-plan". With a shortfall the answer holds the options in `pending`; nothing moves until one is chosen. */
export const replanNow = () => post<StudyPlanReplanned>('/today/planner/replan/')

export const chooseReplanOption = (eventId: string, option: OptionChoice) =>
  post<StudyPlanReplanned>('/today/planner/options/', { event_id: eventId, option })

export const getReplanEvents = (limit = 20) => api<{ events: ReplanEvent[] }>(`/today/planner/events/?limit=${limit}`)

// ---- day feedback, budget suggestion, bonus --------------------------------------------------------------------------------

export const sendFeedback = (rating: FeedbackRating, date?: string) =>
  post<FeedbackResponse>('/today/plan/feedback/', date ? { rating, date } : { rating })

export const getBudgetSuggestion = () => api<BudgetSuggestionResponse>('/today/budget-suggestion/')

export const answerBudgetSuggestion = (accept: boolean) =>
  post<BudgetSuggestionResponse>('/today/budget-suggestion/', { accept })

/** "Do a little more": the plan again, with `bonus.added` bonus tasks. 409 `bonus_not_available` has `details.reason`. */
export const addBonus = () => post<Plan & { bonus: { added: number } }>('/today/plan/bonus/')
