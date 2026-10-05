import { useMutation, useQueryClient } from '@tanstack/react-query'

import { track } from '~/modules/observability'

import {
  catchup,
  createEnrollment,
  deleteCoverage,
  newClientId,
  resetSettings,
  saveSettings,
  setElectives,
  setSubjectExclusion,
  updateEnrollment,
} from '../lib/api'
import { coverageKeys } from '../lib/keys'
import { notify } from '../lib/notify'
import type { CoverageSettings, Overview } from '../lib/types'

const refreshAll = (qc: ReturnType<typeof useQueryClient>) => qc.invalidateQueries({ queryKey: coverageKeys.all })

export function useCreateEnrollment() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: createEnrollment,
    onSuccess: (e) => {
      track('enrollment_created', {
        course: e.course.code,
        level: e.level.code,
        scheme: e.scheme.code,
        term: e.target_term?.code ?? null,
      })
      notify.enrolled()
      return refreshAll(qc)
    },
    onError: (error) =>
      notify.failed(error, 'We could not create your syllabus map. Please try again.', 'coverage-enroll'),
  })
}

export function useCatchup() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (input: { chapterIds: string[]; alsoRevised: boolean }) =>
      catchup({ chapter_ids: input.chapterIds, also_revised: input.alsoRevised, client_id: newClientId() }),
    onSuccess: async (result, input) => {
      track('coverage_catchup_completed', {
        chapters_count: input.chapterIds.length,
        resulting_percent: result.overview.level.pct_simple,
      })
      qc.setQueryData<Overview>(coverageKeys.overview, result.overview)
      notify.catchupApplied(input.chapterIds.length)
      await refreshAll(qc)
    },
    onError: (error) => notify.failed(error, 'We could not apply that. Please try again.', 'coverage-catchup'),
  })
}

export function useSetElectives() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ enrollmentId, choices }: { enrollmentId: string; choices: Record<string, string | null> }) =>
      setElectives(enrollmentId, choices),
    onSuccess: (result, { choices }) => {
      track('electives_chosen', { slots: Object.keys(choices).length, cleared: Object.values(choices).includes(null) })
      qc.setQueryData<Overview>(coverageKeys.overview, result.overview)
      notify.electiveSaved()
      return refreshAll(qc)
    },
    onError: (error) => notify.failed(error, 'We could not save your elective. Please try again.', 'coverage-elective'),
  })
}

interface SubjectExclusionInput {
  subjectId: string
  excluded: boolean
  subjectKey: string
  /** For the message ("Excluded Taxation.") and its Undo. */
  subjectName: string
}

export function useSetSubjectExclusion() {
  const qc = useQueryClient()
  const mutation = useMutation({
    mutationFn: ({ subjectId, excluded }: SubjectExclusionInput) => setSubjectExclusion(subjectId, excluded),
    onSuccess: (result, input) => {
      if (input.excluded) {
        track('chapter_excluded', { subject_key: input.subjectKey })
        notify.excluded(input.subjectName, () => mutation.mutate({ ...input, excluded: false }))
      } else {
        notify.included(input.subjectName)
      }
      qc.setQueryData<Overview>(coverageKeys.overview, result.overview)
      return refreshAll(qc)
    },
    onError: (error) => notify.exclusionFailed(error),
  })
  return mutation
}

export function useSaveSettings() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (next: { settings: CoverageSettings; previous?: CoverageSettings }) => saveSettings(next.settings),
    onSuccess: (saved, { previous }) => {
      const changed = previous
        ? (Object.keys(saved) as Array<keyof CoverageSettings>).filter(
            (k) => JSON.stringify(saved[k]) !== JSON.stringify(previous[k]),
          )
        : []
      track('coverage_settings_changed', { changed_keys: changed })
      notify.settingsSaved()
      qc.setQueryData(coverageKeys.settings, saved)
      return refreshAll(qc)
    },
    onError: (error) =>
      notify.failed(
        error,
        'We could not save your settings. Please check the values and try again.',
        'coverage-settings',
      ),
  })
}

export function useResetSettings() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: resetSettings,
    onSuccess: (saved) => {
      track('coverage_settings_changed', { changed_keys: ['reset'] })
      notify.settingsReset()
      qc.setQueryData(coverageKeys.settings, saved)
      return refreshAll(qc)
    },
    onError: (error) =>
      notify.failed(error, 'We could not restore the defaults. Please try again.', 'coverage-settings'),
  })
}

export function useSwitchScheme() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (input: {
      enrollmentId: string
      schemeId: string
      fromCode: string
      toCode: string
      /** For the message ("Switched to 2023 Scheme."). */
      toName: string
      termId?: string | null
    }) =>
      updateEnrollment(input.enrollmentId, {
        scheme: input.schemeId,
        ...(input.termId ? { target_term: input.termId } : {}),
      }),
    onSuccess: (result, input) => {
      track('scheme_switched', {
        from: input.fromCode,
        to: input.toCode,
        carried_count: result.switch_summary?.carried_chapters ?? 0,
        new_count: result.switch_summary?.new_chapters ?? 0,
      })
      notify.switchedScheme(input.toName)
      return refreshAll(qc)
    },
    onError: (error) => notify.failed(error, 'We could not switch scheme. Please try again.', 'coverage-switch'),
  })
}

export function useUpdateEnrollment() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (input: { id: string; patch: Parameters<typeof updateEnrollment>[1] }) =>
      updateEnrollment(input.id, input.patch),
    onSuccess: () => refreshAll(qc),
    onError: (error) => notify.failed(error, 'We could not save that. Please try again.'),
  })
}

export function useDeleteCoverageData() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: deleteCoverage,
    onSuccess: () => {
      notify.dataDeleted()
      qc.removeQueries({ queryKey: coverageKeys.all })
    },
    onError: (error) => notify.failed(error, 'We could not delete your data. Please try again.', 'coverage-delete'),
  })
}
