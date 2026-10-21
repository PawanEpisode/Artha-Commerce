import React from 'react'

import type { AttemptSectionState } from '../lib/types'
import { CountdownTimer } from './CountdownTimer'

interface SectionStripProps {
  sections: AttemptSectionState[]
  activeSectionKey: string | null
  currentSectionKey: string
  sectionTiming: 'none' | 'flexible' | 'strict_sequential'
  sectionRemainingMs: number
  onSelectSection: (key: string) => void
  onCloseSection?: (key: string) => void
  className?: string
}

export const SectionStrip: React.FC<SectionStripProps> = ({
  sections,
  activeSectionKey,
  currentSectionKey,
  sectionTiming,
  sectionRemainingMs,
  onSelectSection,
  onCloseSection,
  className = '',
}) => {
  const isSequential = sectionTiming === 'strict_sequential'

  return (
    <div className={`flex flex-wrap items-center justify-between gap-4 border-b bg-muted/30 p-2 ${className}`}>
      <div className="flex items-center gap-2 overflow-x-auto">
        {sections.map((sec) => {
          const isSelected = sec.key === currentSectionKey
          const isClosed = sec.status === 'closed'
          const isLocked = isSequential && sec.status === 'pending'

          let btnClasses = 'px-4 py-2 rounded-lg text-sm font-medium transition-all min-h-[44px] '
          if (isSelected) {
            btnClasses += 'bg-primary text-primary-foreground shadow-xs'
          } else if (isClosed) {
            btnClasses += 'bg-muted/60 text-muted-foreground line-through cursor-not-allowed opacity-60'
          } else if (isLocked) {
            btnClasses += 'bg-muted/40 text-muted-foreground cursor-not-allowed opacity-60'
          } else {
            btnClasses += 'bg-card text-foreground border hover:bg-muted/50'
          }

          return (
            <button
              key={sec.key}
              type="button"
              disabled={isClosed || isLocked}
              onClick={() => onSelectSection(sec.key)}
              className={btnClasses}
            >
              Section {sec.key}: {sec.title} ({sec.max_score}M)
              {isClosed && <span className="ml-1.5 text-xs font-normal text-rose-500">[Closed]</span>}
            </button>
          )
        })}
      </div>

      {/* Sequential Section Timer & Close Action */}
      {isSequential && sectionRemainingMs > 0 && (
        <div className="flex items-center gap-3">
          <CountdownTimer remainingMs={sectionRemainingMs} label="Section Timer" warningThresholdMs={180_000} />
          {onCloseSection && activeSectionKey && (
            <button
              type="button"
              onClick={() => {
                if (
                  window.confirm(
                    `Are you sure you want to finish Section ${activeSectionKey}? Once closed, you cannot return to this section.`,
                  )
                ) {
                  onCloseSection(activeSectionKey)
                }
              }}
              className="min-h-[44px] rounded-lg border border-rose-300 bg-rose-50 px-3 py-1.5 text-xs font-semibold text-rose-700 hover:bg-rose-100 dark:border-rose-800 dark:bg-rose-950 dark:text-rose-300"
            >
              Submit Section
            </button>
          )}
        </div>
      )}
    </div>
  )
}
