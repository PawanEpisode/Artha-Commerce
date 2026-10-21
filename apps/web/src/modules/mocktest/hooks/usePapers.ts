import { useEffect, useState } from 'react'

import { fetchPapers, fetchSeriesList } from '../lib/api'
import type { MockPaperCard, SeriesCard } from '../lib/types'

export function usePapers(filters?: { subject?: string; kind?: string; source?: string }) {
  const [papers, setPapers] = useState<MockPaperCard[]>([])
  const [series, setSeries] = useState<SeriesCard[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<Error | null>(null)

  const subject = filters?.subject
  const kind = filters?.kind
  const source = filters?.source

  useEffect(() => {
    let cancelled = false
    setIsLoading(true)
    setError(null)

    const queryFilters = subject || kind || source ? { subject, kind, source } : undefined

    Promise.all([fetchPapers(queryFilters), fetchSeriesList(subject)])
      .then(([pRes, sRes]) => {
        if (!cancelled) {
          setPapers(pRes.papers)
          setSeries(sRes.series)
          setIsLoading(false)
        }
      })
      .catch((err) => {
        if (!cancelled) {
          setError(err instanceof Error ? err : new Error(String(err)))
          setIsLoading(false)
        }
      })

    return () => {
      cancelled = true
    }
  }, [subject, kind, source])

  return { papers, series, isLoading, error }
}
