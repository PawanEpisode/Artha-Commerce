export { ChapterContainer, type ChapterSlotContext } from './containers/ChapterContainer'
export { CoverageSettingsContainer } from './containers/CoverageSettingsContainer'
export { OnboardingContainer } from './containers/OnboardingContainer'
export { RevisionContainer } from './containers/RevisionContainer'
export { SubjectContainer, type SubjectSearch } from './containers/SubjectContainer'
export { type MapSearch, SyllabusMapContainer } from './containers/SyllabusMapContainer'
// Shared with the time tracker: the enrolment's subjects (the offline queue lives in ~/lib/offline-queue).
export { useChapterCoverage, useContinue, useDue, useOverview, useSubjectCoverage } from './hooks/useCoverageQueries'
export { isFeatureDisabled as isCoverageOff, isNoEnrollment } from './lib/api'
export { newClientId } from './lib/api'
export { type ChapterCounts, paperSentence, progressSentence } from './lib/progress'
export type { ChapterCoverage, ContinueChapter, Due, DueRow, Overview, SubjectCoverage, SubjectRow } from './lib/types'
// Shared with the personalization flow: the targets controls and rules, so onboarding and Settings read the same.
export { CatchupResult } from './components/CatchupResult'
export { CatchupStep } from './components/CatchupStep'
export { CourseLevelStep, ElectiveStep, TermStep } from './components/OnboardingSteps'
export { TargetsFields } from './components/TargetsFields'
export { useCatchupSubjects } from './hooks/useCatchupSubjects'
export { useCoverageSettings } from './hooks/useCoverageQueries'
export { prefillSelection } from './lib/prefill'
export {
  DEFAULT_PRESETS,
  DEFAULT_TARGETS,
  presetFor,
  presetLabel,
  targetsEqual,
  targetsLine,
  targetsOfPreset,
  targetsValid,
} from './lib/targets'
export type { CoverageSettings, TargetPreset, Targets, TargetsPreset } from './lib/types'
