import { useAuth } from '~/modules/auth'
import { useFeatureFlag } from '~/modules/observability'

import type { FeatureViewer } from '../lib/offers'

/** Signed-in state plus the three tool flags. Guests until the session lookup finishes, so the first paint has a real action. */
export function useFeatureViewer(): FeatureViewer {
  const { user, loading } = useAuth()
  return {
    signedIn: !loading && Boolean(user),
    flags: {
      focus_timer: useFeatureFlag('focus_timer'),
      time_tracker: useFeatureFlag('time_tracker'),
      syllabus_coverage: useFeatureFlag('syllabus_coverage'),
    },
  }
}
