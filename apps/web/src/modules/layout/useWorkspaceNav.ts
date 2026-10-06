import { useFeatureFlag } from '~/modules/observability'

import { SETTINGS_LINKS, STUDY_LINKS, visibleLinks, type WorkspaceFlag } from './workspace-nav'

/** Study tools and settings the signed-in student is allowed to open. */
export function useWorkspaceNav() {
  const enabled: Record<WorkspaceFlag, boolean> = {
    focus_timer: useFeatureFlag('focus_timer'),
    time_tracker: useFeatureFlag('time_tracker'),
    syllabus_coverage: useFeatureFlag('syllabus_coverage'),
    notifications_ui: useFeatureFlag('notifications_ui'),
  }
  return {
    study: visibleLinks(STUDY_LINKS, enabled),
    settings: visibleLinks(SETTINGS_LINKS, enabled),
  }
}
