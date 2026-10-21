import React, { useEffect, useState } from 'react'

import { ResultSummary } from '../components/ResultSummary'
import { fetchAttemptResult } from '../lib/api'
import type { AttemptResult } from '../lib/types'

interface AttemptResultContainerProps {
  attemptId: string
  onReview: (attemptId: string) => void
  onBackToMocks: () => void
}

export const AttemptResultContainer: React.FC<AttemptResultContainerProps> = ({
  attemptId,
  onReview,
  onBackToMocks,
}) => {
  const [result, setResult] = useState<AttemptResult | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<Error | null>(null)

  useEffect(() => {
    let cancelled = false
    setIsLoading(true)

    fetchAttemptResult(attemptId)
      .then((data) => {
        if (!cancelled) {
          setResult(data)
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
  }, [attemptId])

  if (isLoading) {
    return (
      <div className="mx-auto max-w-3xl animate-pulse space-y-6 p-8">
        <div className="h-64 rounded-3xl border bg-muted/40" />
      </div>
    )
  }

  if (error || !result) {
    return (
      <div className="mx-auto max-w-md space-y-4 p-8 text-center">
        <div className="rounded-2xl border border-rose-200 bg-rose-50 p-4 text-sm text-rose-700">
          Failed to load attempt result.
        </div>
        <button
          type="button"
          onClick={onBackToMocks}
          className="min-h-[44px] rounded-xl border px-4 py-2 text-sm font-semibold"
        >
          Back to Mock Tests
        </button>
      </div>
    )
  }

  return (
    <div className="p-4 sm:p-8">
      <ResultSummary result={result} onReview={() => onReview(attemptId)} onBackToMocks={onBackToMocks} />
    </div>
  )
}
