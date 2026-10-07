import { api } from '~/lib/api'

import type { NotesSettings, NotesSettingsPatch } from './library-types'

/** `GET settings/` and the partial `PUT settings/` (colour legend, default colour, page tone, finger draws, OCR). */
export const getNotesSettings = () => api<NotesSettings>('/notes/settings/')
export const putNotesSettings = (patch: NotesSettingsPatch) =>
  api<NotesSettings>('/notes/settings/', { method: 'PUT', body: JSON.stringify(patch) })
