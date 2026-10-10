import { useAuth } from '~/modules/auth'
import { useOverview } from '~/modules/coverage'
import { useFeatureFlag } from '~/modules/observability'
import { useBootstrap } from '~/modules/personalization'
import { useSessionsPage } from '~/modules/tracker'

import type { FeatureViewer } from '../lib/offers'
import { usedTools } from '../lib/usage'

/**
 * Signed-in state, the tool flags and, for a signed-in student, which tools they already use and their course.
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
  }
  const overview = useOverview(signedIn && flags.syllabus_coverage)
  const sessions = useSessionsPage({}, signedIn && flags.time_tracker)
  const pomodoro = useSessionsPage({ source: 'pomodoro' }, signedIn && flags.time_tracker)
  const { data: me } = useBootstrap()

  if (!signedIn) return { signedIn, flags }
  const course = me?.course
  return {
    signedIn,
    flags,
    used: usedTools({
      startedChapters: (overview.data?.level.chapters_started ?? 0) > 0,
      anySession: (sessions.data?.pages[0]?.results.length ?? 0) > 0,
      pomodoroSession: (pomodoro.data?.pages[0]?.results.length ?? 0) > 0,
    }),
    courseName: course ? `${course.course.name} ${course.level.name}` : undefined,
  }
}
