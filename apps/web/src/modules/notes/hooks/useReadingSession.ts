import { useCallback, useEffect, useRef } from 'react'

import { annotationAnalytics } from '../lib/annotation-analytics'

const MIN_SESSION_MS = 3_000

/**
 * `pdf_reading_session_ended`: how long the reader was open, how many different pages it showed and how many marks the
 * student made, all as buckets. Sent when the reader closes or the page is hidden for good, never with a mark's content.
 */
export function useReadingSession() {
  const startedAt = useRef(Date.now())
  const pages = useRef(new Set<number>())
  const added = useRef(0)

  const send = useCallback(() => {
    const durationMs = Date.now() - startedAt.current
    if (durationMs >= MIN_SESSION_MS && pages.current.size > 0)
      annotationAnalytics.readingSessionEnded({
        durationMs,
        pagesViewed: pages.current.size,
        marksAdded: added.current,
      })
    startedAt.current = Date.now()
    pages.current = new Set()
    added.current = 0
  }, [])

  useEffect(() => {
    window.addEventListener('pagehide', send)
    return () => {
      window.removeEventListener('pagehide', send)
      send()
    }
  }, [send])

  return {
    onPage: useCallback((page: number) => void pages.current.add(page), []),
    onMarkAdded: useCallback(() => void (added.current += 1), []),
  }
}
