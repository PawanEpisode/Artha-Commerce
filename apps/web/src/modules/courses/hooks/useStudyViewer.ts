import { useAuth } from '~/modules/auth'
import { useOverview } from '~/modules/coverage'
import { useFeatureFlag } from '~/modules/observability'

import { type StudyViewer, toSnapshot } from '../lib/prompt'

/** Session plus the student's coverage, without calling the API for a guest. */
export function useStudyViewer(): { ready: boolean; study: StudyViewer } {
  const { user, loading } = useAuth()
  const signedIn = !loading && Boolean(user)
  const coverageFlag = useFeatureFlag('syllabus_coverage')
  const overview = useOverview(signedIn && coverageFlag)
  const failed = overview.isError && !overview.noEnrollment && !overview.featureDisabled
  const coverageOn = coverageFlag && !overview.featureDisabled && !failed
  const snapshot = overview.data ? toSnapshot(overview.data) : null
  const waiting = loading || (signedIn && coverageFlag && overview.isLoading)
  return { ready: !waiting, study: { signedIn, coverageOn, snapshot } }
}
