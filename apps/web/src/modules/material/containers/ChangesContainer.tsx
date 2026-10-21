import React from 'react'

import { ChangesView } from '../components/ChangesView'
import { useEditionCompare } from '../hooks/useEditionCompare'

interface ChangesContainerProps {
  workKey: string
  fromEdition: string
  toEdition: string
  onBack: () => void
}

export const ChangesContainer: React.FC<ChangesContainerProps> = ({ workKey, fromEdition, toEdition, onBack }) => {
  const { result, isLoading, error } = useEditionCompare(workKey, fromEdition, toEdition)

  if (isLoading) {
    return (
      <div className="mx-auto max-w-4xl animate-pulse space-y-6 p-4 sm:p-8">
        <div className="h-20 rounded-2xl bg-muted/40" />
        <div className="grid grid-cols-4 gap-3">
          {[1, 2, 3, 4].map((i) => (
            <div key={i} className="h-24 rounded-2xl bg-muted/30" />
          ))}
        </div>
      </div>
    )
  }

  if (error || !result) {
    return (
      <div className="mx-auto max-w-md space-y-4 p-8 text-center">
        <div className="rounded-2xl border border-rose-200 bg-rose-50 p-4 text-sm text-rose-700">
          Failed to load edition diff comparison.
        </div>
        <button
          type="button"
          onClick={onBack}
          className="min-h-[44px] rounded-xl border px-4 py-2 text-sm font-semibold"
        >
          Go Back
        </button>
      </div>
    )
  }

  return <ChangesView compare={result} workTitle={workKey} onBack={onBack} />
}
