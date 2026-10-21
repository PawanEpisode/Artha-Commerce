import { ArrowLeft, ArrowRightLeft, CheckCircle2, FileEdit, MinusCircle, PlusCircle } from '@artha/design-system'
import React, { useMemo, useState } from 'react'

import type { ChangeType, CompareResult, EditionDiffItem } from '../lib/types'

interface ChangesViewProps {
  compare: CompareResult
  workTitle: string
  onBack: () => void
}

type FilterType = 'all' | ChangeType

export const ChangesView: React.FC<ChangesViewProps> = ({ compare, workTitle, onBack }) => {
  const [activeFilter, setActiveFilter] = useState<FilterType>('all')

  const filteredItems = useMemo(() => {
    if (activeFilter === 'all') return compare.items
    return compare.items.filter((item) => item.change_type === activeFilter)
  }, [compare.items, activeFilter])

  const { summary } = compare

  return (
    <div className="mx-auto max-w-4xl space-y-6 p-4 sm:p-8">
      {/* Header */}
      <div>
        <button
          type="button"
          onClick={onBack}
          className="mb-3 inline-flex min-h-[44px] items-center gap-2 text-sm text-muted-foreground hover:text-foreground"
        >
          <ArrowLeft className="h-4 w-4" />
          Back to Material
        </button>
        <h1 className="text-2xl font-bold tracking-tight text-foreground">What Changed Between Editions</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Comparing {compare.from_edition} vs {compare.to_edition} for {workTitle}
        </p>
      </div>

      {/* Summary KPI Cards */}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <div className="space-y-1 rounded-2xl border bg-card p-4">
          <div className="text-xs font-medium text-muted-foreground">Added Items</div>
          <div className="text-2xl font-bold text-emerald-600">+{summary.added}</div>
        </div>
        <div className="space-y-1 rounded-2xl border bg-card p-4">
          <div className="text-xs font-medium text-muted-foreground">Removed Items</div>
          <div className="text-2xl font-bold text-rose-600">-{summary.removed}</div>
        </div>
        <div className="space-y-1 rounded-2xl border bg-card p-4">
          <div className="text-xs font-medium text-muted-foreground">Modified Items</div>
          <div className="text-2xl font-bold text-amber-600">~{summary.modified}</div>
        </div>
        <div className="space-y-1 rounded-2xl border bg-card p-4">
          <div className="text-xs font-medium text-muted-foreground">Reordered Items</div>
          <div className="text-2xl font-bold text-purple-600">{summary.reordered}</div>
        </div>
      </div>

      {/* Filter Tabs */}
      <div className="flex flex-wrap gap-2" role="tablist" aria-label="Change type filter">
        {(
          [
            { id: 'all', label: 'All Items', count: compare.items.length },
            { id: 'added', label: 'Added', count: summary.added },
            { id: 'removed', label: 'Removed', count: summary.removed },
            { id: 'modified', label: 'Modified', count: summary.modified },
            { id: 'reordered', label: 'Reordered', count: summary.reordered },
          ] as const
        ).map((tab) => {
          const isActive = activeFilter === tab.id
          return (
            <button
              key={tab.id}
              type="button"
              role="tab"
              aria-selected={isActive}
              onClick={() => setActiveFilter(tab.id)}
              className={`flex min-h-[44px] items-center gap-2 rounded-xl border px-3.5 py-2 text-xs font-semibold transition-all ${
                isActive
                  ? 'border-foreground bg-foreground text-background shadow-xs'
                  : 'border-border bg-background text-foreground hover:bg-muted/50'
              }`}
            >
              <span>{tab.label}</span>
              <span
                className={`rounded-md px-1.5 py-0.5 text-[10px] ${
                  isActive ? 'bg-background/20 text-background' : 'bg-muted text-muted-foreground'
                }`}
              >
                {tab.count}
              </span>
            </button>
          )
        })}
      </div>

      {/* Changes Item List */}
      <div className="space-y-3">
        {filteredItems.length === 0 ? (
          <div className="rounded-2xl border bg-muted/10 py-12 text-center text-sm text-muted-foreground">
            No items in this category.
          </div>
        ) : (
          filteredItems.map((item, index) => <DiffItemRow key={item.stable_key || index} item={item} />)
        )}
      </div>
    </div>
  )
}

const DiffItemRow: React.FC<{ item: EditionDiffItem }> = ({ item }) => {
  const getChangeBadge = () => {
    switch (item.change_type) {
      case 'added':
        return (
          <span className="inline-flex items-center gap-1 rounded-full border border-emerald-200 bg-emerald-50 px-2.5 py-1 text-xs font-semibold text-emerald-800">
            <PlusCircle className="h-3.5 w-3.5 text-emerald-600" /> Added in new edition
          </span>
        )
      case 'removed':
        return (
          <span className="inline-flex items-center gap-1 rounded-full border border-rose-200 bg-rose-50 px-2.5 py-1 text-xs font-semibold text-rose-800">
            <MinusCircle className="h-3.5 w-3.5 text-rose-600" /> Removed
          </span>
        )
      case 'modified':
        return (
          <span className="inline-flex items-center gap-1 rounded-full border border-amber-200 bg-amber-50 px-2.5 py-1 text-xs font-semibold text-amber-800">
            <FileEdit className="h-3.5 w-3.5 text-amber-600" /> Content / Page Modified
          </span>
        )
      case 'reordered':
        return (
          <span className="inline-flex items-center gap-1 rounded-full border border-purple-200 bg-purple-50 px-2.5 py-1 text-xs font-semibold text-purple-800">
            <ArrowRightLeft className="h-3.5 w-3.5 text-purple-600" /> Reordered
          </span>
        )
      default:
        return (
          <span className="inline-flex items-center gap-1 rounded-full border bg-muted px-2.5 py-1 text-xs font-medium text-muted-foreground">
            <CheckCircle2 className="h-3.5 w-3.5" /> Unchanged
          </span>
        )
    }
  }

  return (
    <div className="flex flex-col justify-between gap-3 rounded-2xl border bg-card p-4 shadow-xs sm:flex-row sm:items-center">
      <div className="space-y-1">
        <div className="flex items-center gap-2">
          <span className="text-sm font-bold text-foreground">{item.canonical_label}</span>
          {getChangeBadge()}
        </div>
        {item.title && <p className="text-xs text-muted-foreground">{item.title}</p>}
        {item.notes && <p className="pt-0.5 text-xs text-amber-800/90 italic">{item.notes}</p>}
      </div>

      <div className="shrink-0 self-start rounded-lg border bg-muted/40 px-2.5 py-1 font-mono text-xs text-muted-foreground sm:self-auto">
        {item.old_page && item.new_page ? (
          <span>
            p. {item.old_page} → p. {item.new_page}
          </span>
        ) : item.new_page ? (
          <span>p. {item.new_page}</span>
        ) : item.old_page ? (
          <span className="line-through">p. {item.old_page}</span>
        ) : (
          <span>Page N/A</span>
        )}
      </div>
    </div>
  )
}
