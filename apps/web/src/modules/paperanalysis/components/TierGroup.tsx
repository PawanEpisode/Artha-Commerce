import { ChevronDown, ChevronUp } from '@artha/design-system'
import * as React from 'react'

import type { ParetoTier, ScoredChapter } from '../types'
import { PriorityRow } from './PriorityRow'

export interface TierGroupProps {
  tier: ParetoTier
  title: string
  description: string
  chapters: ScoredChapter[]
  subjectKey: string
  defaultOpen?: boolean
}

export function TierGroup({
  tier: _tier,
  title,
  description,
  chapters,
  subjectKey,
  defaultOpen = true,
}: TierGroupProps) {
  const [open, setOpen] = React.useState(defaultOpen)

  if (chapters.length === 0) return null

  return (
    <div className="overflow-hidden rounded-xl border border-border bg-card/60 shadow-xs">
      <button
        type="button"
        onClick={() => setOpen(!open)}
        className="flex w-full items-center justify-between bg-muted/30 px-4 py-3 text-left transition-colors hover:bg-muted/50"
        aria-expanded={open}
      >
        <div className="flex items-center gap-2">
          <span className="text-sm font-semibold text-foreground">{title}</span>
          <span className="text-xs font-normal text-muted-foreground">({chapters.length})</span>
          <span className="hidden text-xs text-muted-foreground/80 sm:inline-block">· {description}</span>
        </div>
        <div className="flex items-center gap-1.5 text-muted-foreground">
          {open ? <ChevronUp className="size-4" /> : <ChevronDown className="size-4" />}
        </div>
      </button>

      {open && (
        <div className="space-y-3 p-4">
          {chapters.map((ch) => (
            <PriorityRow key={ch.chapter_id} chapter={ch} subjectKey={subjectKey} />
          ))}
        </div>
      )}
    </div>
  )
}
