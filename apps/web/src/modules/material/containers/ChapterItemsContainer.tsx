import { ArrowLeft } from '@artha/design-system'
import React from 'react'

import { MaterialPanel } from '../components/MaterialPanel'
import type { MaterialItem } from '../lib/types'

interface ChapterItemsContainerProps {
  workKey: string
  chapterKey: string
  onBackToWork: (workKey: string) => void
  onSelectItem: (item: MaterialItem) => void
}

export const ChapterItemsContainer: React.FC<ChapterItemsContainerProps> = ({
  workKey,
  chapterKey,
  onBackToWork,
  onSelectItem,
}) => {
  return (
    <div className="mx-auto max-w-5xl space-y-6 p-4 sm:p-8">
      {/* Back button */}
      <div>
        <button
          type="button"
          onClick={() => onBackToWork(workKey)}
          className="inline-flex min-h-[44px] items-center gap-2 text-sm text-muted-foreground hover:text-foreground"
        >
          <ArrowLeft className="h-4 w-4" />
          Back to Book Overview
        </button>
      </div>

      {/* Embedded Material Panel */}
      <MaterialPanel workKey={workKey} chapterKey={chapterKey} onSelectItem={onSelectItem} onOpenWork={onBackToWork} />
    </div>
  )
}
