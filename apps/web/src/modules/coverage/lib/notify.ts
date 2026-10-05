/**
 * Every toast of the coverage module, in one place (copy follows the F-16 PRD toast catalogue, section 5.7).
 * Plain sentences under 80 characters, no exclamation marks. Field validation stays inline; a toast announces an
 * outcome the screen does not already show. Failures go through `toastApiError`.
 */
import { toast, toastApiError } from '@artha/design-system'

import { ruleViolation } from './api'
import { type Activity, ACTIVITY_NOUN } from './rules'

const SINGULAR: Record<Activity, string> = { practice: 'Practice set', revisions: 'Revision', mocks: 'Mock test' }
const sentence = (text: string) => text.charAt(0).toUpperCase() + text.slice(1)

export const notify = {
  activityLogged: (activity: Activity, done: number, target: number) =>
    toast.success(`${SINGULAR[activity]} logged: ${Math.min(done, target)} of ${target}.`, { id: 'coverage-log' }),

  /** A manual log the server refused (409). Other failures are reported as errors. */
  logRefused(error: unknown, fallback = 'We could not save that. Please try again.') {
    const rule = ruleViolation(error)
    if (rule?.code === 'target_reached') {
      const { activity, target } = rule.details
      return toast.info(`${sentence(ACTIVITY_NOUN[activity])} are already at target (${target} of ${target}).`, {
        id: 'coverage-log',
      })
    }
    if (rule?.code === 'activity_not_tracked') {
      return toast.info(`${sentence(ACTIVITY_NOUN[rule.details.activity])} are not part of your plan.`, {
        id: 'coverage-log',
      })
    }
    return toastApiError(error, fallback, { id: 'coverage-log' })
  },

  /** Confidence refused (409 `confidence_locked`) or failed. */
  confidenceRefused(error: unknown) {
    const rule = ruleViolation(error)
    if (rule?.code === 'confidence_locked') {
      return toast.info(`Unlocks at ${rule.details.required}% coverage. This chapter is at ${rule.details.current}%.`, {
        id: 'coverage-confidence',
      })
    }
    return toastApiError(error, 'We could not save your confidence. Please try again.', { id: 'coverage-confidence' })
  },
  confidenceSaved: (cleared: boolean) =>
    toast.success(cleared ? 'Confidence cleared.' : 'Confidence saved.', { id: 'coverage-confidence' }),

  topicRead: (topicId: string, read: boolean) =>
    toast.success(read ? 'Marked as read.' : 'Marked as not read.', { id: `coverage-read-${topicId}` }),
  tickFailed: (error: unknown) =>
    toastApiError(error, 'We could not save that tick. It has been put back.', { id: 'coverage-tick' }),
  savedOffline: () => toast.info('Saved on this device. It will sync when you are online.', { id: 'coverage-offline' }),

  excluded: (name: string, undo: () => void) =>
    toast.success(`Excluded ${name}.`, { id: 'coverage-exclusion', action: { label: 'Undo', onClick: undo } }),
  included: (name: string) => toast.success(`Included ${name} again.`, { id: 'coverage-exclusion' }),
  exclusionFailed: (error: unknown) =>
    toastApiError(error, 'We could not change that. Please try again.', { id: 'coverage-exclusion' }),

  catchupApplied: (chapters: number) =>
    toast.success(`Marked ${chapters} ${chapters === 1 ? 'chapter' : 'chapters'} as read.`),
  enrolled: () => toast.success('Your syllabus map is ready.'),
  electiveSaved: () => toast.success('Elective saved.'),
  settingsSaved: () => toast.success('Coverage settings saved.', { id: 'coverage-settings' }),
  settingsReset: () => toast.success('Defaults restored.', { id: 'coverage-settings' }),
  switchedScheme: (scheme: string) => toast.success(`Switched to ${scheme}.`),
  dataExported: () => toast.success('Your coverage data was downloaded.'),
  dataDeleted: () => toast.info('Your coverage data was deleted.'),

  queueSynced: (count: number) => toast.success(`Synced ${count} ${count === 1 ? 'change' : 'changes'}.`),
  queueFailed: (count: number, retry?: () => void) =>
    toast.error(`${count} ${count === 1 ? 'change' : 'changes'} did not sync.`, {
      id: 'coverage-queue-failed',
      action: retry ? { label: 'Retry', onClick: retry } : undefined,
    }),
  /** A queued log the server rejected because the target was reached in the meantime. */
  queuedLogSkipped: (activity: Activity, chapterName?: string) =>
    toast.info(
      chapterName
        ? `Skipped a ${SINGULAR[activity].toLowerCase()} for ${chapterName}: already at target.`
        : `Skipped a ${SINGULAR[activity].toLowerCase()}: already at target.`,
    ),

  failed: (error: unknown, fallback: string, id?: string) => toastApiError(error, fallback, id ? { id } : undefined),
}
