import { useAuth } from '~/modules/auth'
import { useOverview } from '~/modules/coverage'
import { useFeatureFlag } from '~/modules/observability'
import { useSessionsPage } from '~/modules/tracker'

import type { FeatureViewer } from '../lib/offers'
import { usedTools } from '../lib/usage'

/**
 * Signed-in state, the tool flags and, for a signed-in student, which tools they already use.
 * Guests until the session lookup finishes, so the first paint has a real action and the guest page never reorders.
 */
export function useFeatureViewer(): FeatureViewer {
  const { user, loading } = useAuth()
  const signedIn = !loading && Boolean(user)
  const flags = {
    focus_timer: useFeatureFlag('focus_timer'),
    time_tracker: useFeatureFlag('time_tracker'),
    syllabus_coverage: useFeatureFlag('syllabus_coverage'),
    notes: useFeatureFlag('notes'),
    // Fails closed, like the nav link: the card says Coming soon until PostHog explicitly turns the flag on.
    recall_system: useFeatureFlag('recall_system', { strict: true }),
    pyq_bank: useFeatureFlag('pyq_bank', { strict: true }),
    question_bank: useFeatureFlag('question_bank', { strict: true }),
    mcq_bank: useFeatureFlag('mcq_bank', { strict: true }),
    amendments: useFeatureFlag('amendments', { strict: true }),
    mock_tests: useFeatureFlag('mock_tests'),
    study_material: useFeatureFlag('study_material'),
  }
  const overview = useOverview(signedIn && flags.syllabus_coverage)
  const sessions = useSessionsPage({}, signedIn && flags.time_tracker)
  const pomodoro = useSessionsPage({ source: 'pomodoro' }, signedIn && flags.time_tracker)

  if (!signedIn) return { signedIn, flags }
  return {
    signedIn,
    flags,
    used: usedTools({
      startedChapters: (overview.data?.level.chapters_started ?? 0) > 0,
      anySession: (sessions.data?.pages[0]?.results.length ?? 0) > 0,
      pomodoroSession: (pomodoro.data?.pages[0]?.results.length ?? 0) > 0,
    }),
  }
}
