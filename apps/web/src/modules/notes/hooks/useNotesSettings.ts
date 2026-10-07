import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { notesAnalytics } from '../lib/analytics'
import { notesKeys } from '../lib/keys'
import type { NotesSettings, NotesSettingsPatch } from '../lib/library-types'
import { getNotesSettings, putNotesSettings } from '../lib/settings-api'

/** `GET settings/`: legend, default colour, page tone, finger draws, OCR default and language. Stays open when the flag is off. */
export const useNotesSettings = (enabled = true) =>
  useQuery({ queryKey: notesKeys.settings, queryFn: getNotesSettings, enabled, staleTime: 5 * 60_000 })

/** Saves a partial change at once on screen, rolls back if the server refuses, and reports only which keys changed. */
export function useUpdateNotesSettings() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (patch: NotesSettingsPatch) => putNotesSettings(patch),
    onMutate: async (patch) => {
      await qc.cancelQueries({ queryKey: notesKeys.settings })
      const before = qc.getQueryData<NotesSettings>(notesKeys.settings)
      if (before) qc.setQueryData(notesKeys.settings, { ...before, ...patch })
      return { before }
    },
    onError: (_error, _patch, context) => {
      if (context?.before) qc.setQueryData(notesKeys.settings, context.before)
    },
    onSuccess: (saved, patch) => {
      qc.setQueryData(notesKeys.settings, saved)
      notesAnalytics.settingsChanged(Object.keys(patch))
    },
  })
}
