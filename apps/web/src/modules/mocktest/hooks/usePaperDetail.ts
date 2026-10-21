import { useEffect, useState } from 'react'

import { fetchPaper } from '../lib/api'
import type { PaperDetail } from '../lib/types'

export function usePaperDetail(paperId: string) {
  const [paper, setPaper] = useState<PaperDetail | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<Error | null>(null)

  useEffect(() => {
    let cancelled = false
    setIsLoading(true)
    setError(null)

    fetchPaper(paperId)
      .then((data) => {
        if (!cancelled) {
          setPaper(data)
          setIsLoading(false)
        }
      })
      .catch((err) => {
        if (!cancelled) {
          setError(err)
          setIsLoading(false)
        }
      })

    return () => {
      cancelled = true
    }
  }, [paperId])

  return { paper, isLoading, error }
}
