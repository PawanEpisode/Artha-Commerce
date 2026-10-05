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
      return refreshAll(qc)
    },
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
      await refreshAll(qc)
    },
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
      return refreshAll(qc)
    },
  })
}

export function useSetSubjectExclusion() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ subjectId, excluded }: { subjectId: string; excluded: boolean; subjectKey: string }) =>
      setSubjectExclusion(subjectId, excluded),
    onSuccess: (result, { excluded, subjectKey }) => {
      if (excluded) track('chapter_excluded', { subject_key: subjectKey })
      qc.setQueryData<Overview>(coverageKeys.overview, result.overview)
      return refreshAll(qc)
    },
  })
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
      qc.setQueryData(coverageKeys.settings, saved)
      return refreshAll(qc)
    },
  })
}

export function useResetSettings() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: resetSettings,
    onSuccess: (saved) => {
      track('coverage_settings_changed', { changed_keys: ['reset'] })
      qc.setQueryData(coverageKeys.settings, saved)
      return refreshAll(qc)
    },
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
      return refreshAll(qc)
    },
  })
}

export function useUpdateEnrollment() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (input: { id: string; patch: Parameters<typeof updateEnrollment>[1] }) =>
      updateEnrollment(input.id, input.patch),
    onSuccess: () => refreshAll(qc),
  })
}

export function useDeleteCoverageData() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: deleteCoverage,
    onSuccess: () => {
      qc.removeQueries({ queryKey: coverageKeys.all })
    },
  })
}
