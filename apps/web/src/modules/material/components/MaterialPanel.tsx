import { BookOpen, CheckCircle2, ExternalLink, RotateCcw, Search } from '@artha/design-system'
import React, { useMemo, useState } from 'react'

import { useChapterItems } from '../hooks/useChapterItems'
import type { ItemKind, MaterialItem, ProgressState } from '../lib/types'
import { ItemRow } from './ItemRow'

interface MaterialPanelProps {
  workKey: string
  chapterKey: string
  onSelectItem?: (item: MaterialItem) => void
  onOpenWork?: (workKey: string) => void
}

type FilterOption = 'all' | 'done' | 'revise' | 'to_do' | ItemKind

export const MaterialPanel: React.FC<MaterialPanelProps> = ({ workKey, chapterKey, onSelectItem, onOpenWork }) => {
  const { data, items, summary, isLoading, error, setProgress, reportItem } = useChapterItems(workKey, chapterKey)

  const [searchQuery, setSearchQuery] = useState('')
  const [activeFilter, setActiveFilter] = useState<FilterOption>('all')

  const filteredItems = useMemo(() => {
    return items.filter((item) => {
      // Search match
      if (searchQuery.trim()) {
        const q = searchQuery.toLowerCase()
        const matchLabel = item.canonical_label?.toLowerCase().includes(q)
        const matchTitle = item.title?.toLowerCase().includes(q)
        const matchNote = item.note?.toLowerCase().includes(q)
        if (!matchLabel && !matchTitle && !matchNote) return false
      }

      // Filter match
      if (activeFilter === 'all') return true
      if (activeFilter === 'done') return item.progress === 'done'
      if (activeFilter === 'revise') return item.progress === 'revise'
      if (activeFilter === 'to_do') return !item.progress || item.progress === 'to_do'
      return item.kind === activeFilter
    })
  }, [items, searchQuery, activeFilter])

  if (isLoading) {
    return (
      <div className="animate-pulse space-y-4 rounded-3xl border bg-card p-6">
        <div className="h-6 w-1/3 rounded-lg bg-muted/50" />
        <div className="h-20 rounded-2xl bg-muted/40" />
        <div className="space-y-2">
          <div className="h-16 rounded-xl bg-muted/30" />
          <div className="h-16 rounded-xl bg-muted/30" />
        </div>
      </div>
    )
  }

  if (error || !data) {
    return (
      <div className="space-y-3 rounded-3xl border bg-card p-6 text-center">
        <div className="text-sm text-muted-foreground">
          Study material checklist not available for this chapter yet.
        </div>
        {onOpenWork && (
          <button
            type="button"
            onClick={() => onOpenWork(workKey)}
            className="text-xs font-semibold text-primary hover:underline"
          >
            Browse Study Material Library →
          </button>
        )}
      </div>
    )
  }

  const completionPct = summary?.completion_pct ?? 0

  return (
    <div className="space-y-5 rounded-3xl border bg-card p-5 shadow-xs sm:p-6">
      {/* Header with Title & Edition */}
      <div className="flex flex-col justify-between gap-3 border-b pb-4 sm:flex-row sm:items-center">
        <div className="space-y-1">
          <div className="flex items-center gap-2">
            <BookOpen className="h-4 w-4 text-primary" />
            <h2 className="text-base font-bold text-foreground">Official Study Material Checklist</h2>
          </div>
          <p className="text-xs text-muted-foreground">
            {data.work_title} • {data.edition_label}
          </p>
        </div>

        {onOpenWork && (
          <button
            type="button"
            onClick={() => onOpenWork(workKey)}
            className="inline-flex min-h-[44px] items-center gap-1.5 text-xs font-semibold text-muted-foreground hover:text-foreground"
          >
            <span>Full Book Overview</span>
            <ExternalLink className="h-3.5 w-3.5" />
          </button>
        )}
      </div>

      {/* Progress Metric Card */}
      <div className="space-y-2.5 rounded-2xl border bg-muted/20 p-4">
        <div className="flex items-center justify-between text-xs font-semibold">
          <span className="text-foreground">Chapter Practice Progress</span>
          <span className="font-mono text-primary">{completionPct}% Completed</span>
        </div>

        {/* Progress Bar */}
        <div
          role="progressbar"
          aria-valuenow={completionPct}
          aria-valuemin={0}
          aria-valuemax={100}
          aria-label="Chapter completion progress"
          className="flex h-2 w-full overflow-hidden rounded-full bg-muted"
        >
          <div className="bg-emerald-600 transition-all duration-300" style={{ width: `${completionPct}%` }} />
        </div>

        {/* Stats Row */}
        <div className="flex items-center justify-between pt-1 text-xs text-muted-foreground">
          <div className="flex items-center gap-1.5">
            <CheckCircle2 className="h-3.5 w-3.5 text-emerald-600" />
            <span>
              Done: <strong className="text-foreground">{summary?.done || 0}</strong>
            </span>
          </div>
          <div className="flex items-center gap-1.5">
            <RotateCcw className="h-3.5 w-3.5 text-amber-600" />
            <span>
              Revise: <strong className="text-foreground">{summary?.revise || 0}</strong>
            </span>
          </div>
          <div>
            To Do: <strong className="text-foreground">{summary?.to_do || items.length}</strong>
          </div>
          <div>
            Total: <strong className="text-foreground">{summary?.total || items.length}</strong>
          </div>
        </div>
      </div>

      {/* Search and Filters */}
      <div className="space-y-3">
        <div className="relative">
          <Search className="pointer-events-none absolute top-1/2 left-3.5 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <input
            type="search"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Filter by label or keyword (e.g. Illustration 4, deferred tax)..."
            className="min-h-[44px] w-full rounded-xl border bg-background py-2 pr-4 pl-10 text-xs focus:ring-2 focus:ring-primary focus:outline-hidden"
          />
        </div>

        {/* Quick Filter Pills */}
        <div className="flex flex-wrap gap-1.5" role="tablist" aria-label="Item kind filter">
          {(
            [
              { id: 'all', label: 'All Items' },
              { id: 'illustration', label: 'Illustrations' },
              { id: 'exercise', label: 'Exercises' },
              { id: 'tyk', label: 'Test Your Knowledge' },
              { id: 'concept', label: 'Concepts' },
              { id: 'done', label: 'Done' },
              { id: 'revise', label: 'Revise' },
              { id: 'to_do', label: 'To Do' },
            ] as const
          ).map((filter) => {
            const isActive = activeFilter === filter.id
            return (
              <button
                key={filter.id}
                type="button"
                role="tab"
                aria-selected={isActive}
                onClick={() => setActiveFilter(filter.id)}
                className={`min-h-[36px] rounded-lg border px-3 py-1 text-xs font-medium transition-colors ${
                  isActive
                    ? 'border-foreground bg-foreground font-semibold text-background shadow-xs'
                    : 'border-border bg-background text-muted-foreground hover:bg-muted/50'
                }`}
              >
                {filter.label}
              </button>
            )
          })}
        </div>
      </div>

      {/* Items List */}
      <div className="space-y-2.5">
        {filteredItems.length === 0 ? (
          <div className="rounded-2xl border bg-muted/10 py-8 text-center text-xs text-muted-foreground">
            No study material items found matching your filters.
          </div>
        ) : (
          filteredItems.map((item) => (
            <ItemRow
              key={item.id}
              item={item}
              onStateChange={async (state: ProgressState, note?: string) => {
                await setProgress(item.id, state, note)
              }}
              onReport={async (payload) => {
                await reportItem(item.id, payload)
              }}
              onSelect={onSelectItem}
            />
          ))
        )}
      </div>
    </div>
  )
}
