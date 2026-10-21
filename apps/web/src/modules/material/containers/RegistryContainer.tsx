import { ArrowLeft } from '@artha/design-system'
import React from 'react'

import { CourseRegistryForm } from '../components/CourseRegistryForm'

interface RegistryContainerProps {
  onBack: () => void
}

export const RegistryContainer: React.FC<RegistryContainerProps> = ({ onBack }) => {
  return (
    <div className="mx-auto max-w-4xl space-y-6 p-4 sm:p-8">
      <div>
        <button
          type="button"
          onClick={onBack}
          className="mb-3 inline-flex min-h-[44px] items-center gap-2 text-sm text-muted-foreground hover:text-foreground"
        >
          <ArrowLeft className="h-4 w-4" />
          Back to Study Material
        </button>
        <h1 className="text-2xl font-bold tracking-tight text-foreground">
          Study Material Preferences & Institute Registry
        </h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Select followed institutes, manage active editions, and control learning data privacy.
        </p>
      </div>

      <CourseRegistryForm />
    </div>
  )
}
