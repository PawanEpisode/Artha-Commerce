import { useCallback, useEffect, useState } from 'react'

import { compareEditions } from '../lib/api'
import type { CompareResult } from '../lib/types'

export function useEditionCompare(workKey: string, fromEditionKey: string, toEditionKey: string) {
  const [result, setResult] = useState<CompareResult | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<Error | null>(null)

  const reload = useCallback(() => {
    if (!workKey || !fromEditionKey || !toEditionKey) {
      setResult(null)
      setIsLoading(false)
      return
    }

    setIsLoading(true)
    setError(null)

    compareEditions(workKey, fromEditionKey, toEditionKey)
      .then((data) => {
        setResult(data)
        setIsLoading(false)
      })
      .catch((err) => {
        setError(err)
        setIsLoading(false)
      })
  }, [workKey, fromEditionKey, toEditionKey])

  useEffect(() => {
    reload()
  }, [reload])

  return {
    result,
    isLoading,
    error,
    reload,
  }
}
