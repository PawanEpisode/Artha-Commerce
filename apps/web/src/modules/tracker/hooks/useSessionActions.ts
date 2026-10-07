import { useMutation, useQueryClient } from '@tanstack/react-query'

import { QueuedOffline, writeOrQueue } from '~/lib/offline-queue'
import { track } from '~/modules/observability'

import {
  addManual,
  deleteSession,
  editSession,
  manualRequest,
  mergeSessions,
  putGoals,
  putSettings,
  splitSession,
  undoAction,
} from '../lib/api'
import { trackerKeys } from '../lib/keys'
import type { GoalEntry, ManualInput, SessionEdit, StudySession, TrackerSettings } from '../lib/types'

/** Every change of study time moves the day totals, goals, reports and (through the forward) coverage. */
function useRefreshAll() {
  const qc = useQueryClient()
  return () => {
    void qc.invalidateQueries({ queryKey: trackerKeys.sessions })
    void qc.invalidateQueries({ queryKey: trackerKeys.goals })
    void qc.invalidateQueries({ queryKey: trackerKeys.reports })
    void qc.invalidateQueries({ queryKey: trackerKeys.offline })
    void qc.invalidateQueries({ queryKey: ['coverage'] })
  }
}

/** Adds a manual entry. When offline the entry is queued with its client id and `queued` comes back true. */
export function useAddManual() {
  const refresh = useRefreshAll()
  return useMutation({
    mutationFn: async (input: ManualInput): Promise<{ session: StudySession | null; queued: boolean }> => {
      const req = manualRequest(input)
      try {
        const session = await writeOrQueue({ clientId: input.client_id, ...req }, () => addManual(input))
        track('manual_entry_added', { activity_type: input.activity_type, has_subject: !!input.subject_id })
        track('session_logged', { source: 'manual' })
        return { session, queued: false }
      } catch (error) {
        if (!(error instanceof QueuedOffline)) throw error
        track('manual_entry_added', { activity_type: input.activity_type, queued: true })
        return { session: null, queued: true }
      }
    },
    onSettled: refresh,
  })
}

export function useEditSession() {
  const refresh = useRefreshAll()
  return useMutation({
    mutationFn: ({ id, patch }: { id: string; patch: SessionEdit }) => editSession(id, patch),
    onSuccess: (_s, { patch }) => track('session_edited', { fields: Object.keys(patch).filter((k) => k !== 'note') }),
    onSettled: refresh,
  })
}

export function useDeleteSession() {
  const refresh = useRefreshAll()
  return useMutation({
    mutationFn: (id: string) => deleteSession(id),
    onSuccess: () => track('session_deleted'),
    onSettled: refresh,
  })
}

export function useUndo() {
  const refresh = useRefreshAll()
  return useMutation({
    mutationFn: ({ token, notes }: { token: string; notes?: Record<string, string> }) => undoAction(token, notes),
    onSuccess: () => track('session_undone'),
    onSettled: refresh,
  })
}

export function useMerge() {
  const refresh = useRefreshAll()
  return useMutation({
    mutationFn: (body: Parameters<typeof mergeSessions>[0]) => mergeSessions(body),
    onSuccess: (_r, body) => track('sessions_merged', { count: body.session_ids.length }),
    onSettled: refresh,
  })
}

export function useSplit() {
  const refresh = useRefreshAll()
  return useMutation({
    mutationFn: ({ id, at }: { id: string; at: string }) => splitSession(id, at),
    onSuccess: () => track('session_split'),
    onSettled: refresh,
  })
}

export function useSaveGoals() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (goals: GoalEntry[]) => putGoals(goals),
    onSuccess: (data) => {
      qc.setQueryData(trackerKeys.goals, data)
      track('goal_set', { count: data.goals.length })
      void qc.invalidateQueries({ queryKey: trackerKeys.reports })
    },
  })
}

export function useSaveSettings() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (patch: Partial<TrackerSettings>) => putSettings(patch),
    onSuccess: (data) => {
      const { changed_keys, ...settings } = data
      qc.setQueryData(trackerKeys.settings, settings)
      track('tracker_settings_changed', { keys: changed_keys })
      void qc.invalidateQueries({ queryKey: trackerKeys.reports })
      void qc.invalidateQueries({ queryKey: trackerKeys.stopwatch })
    },
  })
}
