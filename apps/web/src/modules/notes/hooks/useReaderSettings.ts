import { useQuery } from '@tanstack/react-query'
import { useMemo } from 'react'

import { DEFAULT_LEGEND, type Legend, legendOptions } from '../lib/annotation-legend'
import type { MarkupColor, NotesSettings } from '../lib/annotation-types'
import { getSettings } from '../lib/annotations-api'
import { notesKeys } from '../lib/keys'

export interface ReaderSettings {
  legend: Legend
  options: ReturnType<typeof legendOptions>
  defaultColor: MarkupColor
  fingerDraws: boolean
  /** The card button and badge show only when the server says a recall provider exists (FR-F03-55/56). */
  canCard: boolean
  loaded: boolean
}

/** What the reader needs from `GET settings/`: the colour legend names, the default colour, "finger draws" and capabilities. */
export function useReaderSettings(): ReaderSettings {
  const query = useQuery<NotesSettings>({
    queryKey: notesKeys.settings,
    queryFn: getSettings,
    staleTime: 5 * 60_000,
    retry: 1,
  })
  const data = query.data
  return useMemo(() => {
    const legend = data?.color_legend ?? DEFAULT_LEGEND
    return {
      legend,
      options: legendOptions(legend),
      defaultColor: data?.default_color ?? 'y',
      fingerDraws: data?.finger_draws ?? false,
      canCard: data?.capabilities.recall === true,
      loaded: !!data,
    }
  }, [data])
}
