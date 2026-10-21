import React from 'react'

import { determinePaletteStatus } from '../lib/attempt-machine'
import type { AttemptLayoutItem } from '../lib/types'

interface PalettePanelProps {
  layout: AttemptLayoutItem[]
  currentPosition: number
  answers: Record<number, unknown>
  flags: Record<number, boolean>
  visitedPositions: Set<number>
  onSelectPosition: (pos: number) => void
  className?: string
}

export const PalettePanel: React.FC<PalettePanelProps> = ({
  layout,
  currentPosition,
  answers,
  flags,
  visitedPositions,
  onSelectPosition,
  className = '',
}) => {
  let answeredCount = 0
  let markedCount = 0
  let notAnsweredCount = 0
  let notVisitedCount = 0

  layout.forEach((item) => {
    const hasAnswer = answers[item.pos] !== undefined && answers[item.pos] !== null
    const isFlagged = flags[item.pos] || false
    const isVisited = visitedPositions.has(item.pos)

    const st = determinePaletteStatus({
      isCurrent: item.pos === currentPosition,
      isVisited,
      hasAnswer,
      isFlagged,
    })

    if (st === 'answered' || st === 'marked_answered') answeredCount++
    if (st === 'marked_for_review' || st === 'marked_answered') markedCount++
    if (st === 'not_answered') notAnsweredCount++
    if (st === 'not_visited') notVisitedCount++
  })

  return (
    <div className={`flex flex-col gap-4 rounded-xl border bg-card p-4 shadow-xs ${className}`}>
      <h3 className="text-sm font-semibold text-foreground">Question Palette</h3>

      {/* Grid of question buttons */}
      <div className="grid max-h-[360px] grid-cols-5 gap-2 overflow-y-auto p-1">
        {layout.map((item) => {
          const isCurrent = item.pos === currentPosition
          const hasAnswer = answers[item.pos] !== undefined && answers[item.pos] !== null
          const isFlagged = flags[item.pos] || false
          const isVisited = visitedPositions.has(item.pos)

          const status = determinePaletteStatus({
            isCurrent,
            isVisited,
            hasAnswer,
            isFlagged,
          })

          let bgClasses = 'bg-muted text-muted-foreground'
          if (status === 'answered') {
            bgClasses = 'bg-emerald-600 text-white font-medium hover:bg-emerald-700'
          } else if (status === 'marked_for_review') {
            bgClasses = 'bg-purple-600 text-white font-medium hover:bg-purple-700'
          } else if (status === 'marked_answered') {
            bgClasses = 'bg-purple-600 text-white font-medium hover:bg-purple-700 ring-2 ring-emerald-400'
          } else if (status === 'not_answered') {
            bgClasses = 'bg-amber-500 text-white font-medium hover:bg-amber-600'
          }

          return (
            <button
              key={item.pos}
              type="button"
              onClick={() => onSelectPosition(item.pos)}
              className={`flex min-h-[44px] min-w-[44px] items-center justify-center rounded-lg text-sm transition-all ${bgClasses} ${
                isCurrent ? 'scale-105 shadow-xs ring-2 ring-primary ring-offset-2' : ''
              }`}
              aria-label={`Question ${item.pos}, ${status.replace('_', ' ')}${isCurrent ? ', current' : ''}`}
            >
              {item.pos}
            </button>
          )
        })}
      </div>

      {/* Legend */}
      <div className="grid grid-cols-2 gap-2 border-t pt-3 text-xs text-muted-foreground">
        <div className="flex items-center gap-2">
          <span className="h-3.5 w-3.5 shrink-0 rounded-full bg-emerald-600" />
          <span>Answered ({answeredCount})</span>
        </div>
        <div className="flex items-center gap-2">
          <span className="h-3.5 w-3.5 shrink-0 rounded-full bg-purple-600" />
          <span>Marked ({markedCount})</span>
        </div>
        <div className="flex items-center gap-2">
          <span className="h-3.5 w-3.5 shrink-0 rounded-full bg-amber-500" />
          <span>Not Answered ({notAnsweredCount})</span>
        </div>
        <div className="flex items-center gap-2">
          <span className="h-3.5 w-3.5 shrink-0 rounded-full border bg-muted" />
          <span>Not Visited ({notVisitedCount})</span>
        </div>
      </div>
    </div>
  )
}
