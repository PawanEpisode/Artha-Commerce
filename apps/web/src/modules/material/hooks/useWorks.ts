import { useCallback, useEffect, useState } from 'react'

import { fetchWorks } from '../lib/api'
import type { Work } from '../lib/types'

export interface UseWorksFilters {
  course?: string
  level?: string
  subject?: string
  provider?: string
  q?: string
}

export function useWorks(initialFilters?: UseWorksFilters) {
  const [works, setWorks] = useState<Work[]>([])
  const [filters, setFilters] = useState<UseWorksFilters>(initialFilters || {})
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<Error | null>(null)

  const reload = useCallback(() => {
    setIsLoading(true)
    setError(null)
    fetchWorks(filters)
      .then((data) => {
        const worksList = Array.isArray(data) ? data : ((data as { works?: Work[] })?.works ?? [])
        setWorks(worksList)
        setIsLoading(false)
      })
      .catch((err) => {
        setError(err)
        setIsLoading(false)
      })
  }, [filters])

  useEffect(() => {
    reload()
  }, [reload])

  return {
    works,
    filters,
    setFilters,
    isLoading,
    error,
    reload,
  }
}
