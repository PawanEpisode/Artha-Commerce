import { useFeatureFlag } from '~/modules/observability'
import { useBootstrap } from '~/modules/personalization'

import { SETTINGS_LINKS, STAFF_LINKS, STUDY_LINKS, visibleLinks, type WorkspaceFlag } from './workspace-nav'

/** Study tools and settings the signed-in student is allowed to open. */
export function useWorkspaceNav() {
  const enabled: Record<WorkspaceFlag, boolean> = {
    focus_timer: useFeatureFlag('focus_timer'),
    time_tracker: useFeatureFlag('time_tracker'),
    syllabus_coverage: useFeatureFlag('syllabus_coverage'),
    notifications_ui: useFeatureFlag('notifications_ui'),
    notes: useFeatureFlag('notes'),
    // Fails closed: the link shows only once the flag is known to be on.
    recall_system: useFeatureFlag('recall_system', { strict: true }),
    today_plan: useFeatureFlag('today_plan', { strict: true }),
    today_planner: useFeatureFlag('today_planner', { strict: true }),
    question_bank: useFeatureFlag('question_bank', { strict: true }),
    pyq_bank: useFeatureFlag('pyq_bank', { strict: true }),
    mcq_bank: useFeatureFlag('mcq_bank', { strict: true }),
    performance_analytics: useFeatureFlag('performance_analytics'),
    paper_analysis: useFeatureFlag('paper_analysis', { strict: true }),
    progression_engine: useFeatureFlag('progression_engine'),
  }
  const { data } = useBootstrap()
  return {
    study: visibleLinks(STUDY_LINKS, enabled),
    settings: visibleLinks(SETTINGS_LINKS, enabled),
    /** Editorial and design-system tabs, only for editors and admins. */
    staff: data?.role === 'editor' || data?.role === 'admin' ? STAFF_LINKS : [],
  }
}
