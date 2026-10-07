import { useQueries } from '@tanstack/react-query'
import { useCallback } from 'react'

import { getAttachmentUrl } from '../lib/api'

/**
 * Signed read URLs for the images in a note. They last an hour, so they are cached for 50 minutes and never stored
 * in the note. Returns a lookup for the preview; an id without a URL yet renders as a labelled placeholder.
 */
export function useAttachmentUrls(ids: readonly string[], enabled = true) {
  const urls = useQueries({
    queries: ids.map((id) => ({
      queryKey: ['notes', 'attachment', id],
      queryFn: () => getAttachmentUrl(id).then((r) => r.url),
      staleTime: 50 * 60_000,
      retry: false,
      enabled,
    })),
    combine: (results) => Object.fromEntries(ids.map((id, i) => [id, results[i]?.data as string | undefined])),
  })
  return useCallback((id: string) => urls[id], [urls])
}
