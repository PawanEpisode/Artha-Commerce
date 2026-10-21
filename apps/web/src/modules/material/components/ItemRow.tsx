import { ExternalLink, Flag, MessageSquare, Sparkles } from '@artha/design-system'
import React, { useState } from 'react'

import { getKindMetadata } from '../lib/labels'
import { formatPageRange } from '../lib/locator'
import type { MaterialItem, MaterialReportPayload, ProgressState } from '../lib/types'
import { ReportModal } from './ReportModal'
import { StateToggle } from './StateToggle'

interface ItemRowProps {
  item: MaterialItem
  onStateChange: (state: ProgressState, note?: string) => Promise<void>
  onReport: (payload: MaterialReportPayload) => Promise<void>
  onSelect?: (item: MaterialItem) => void
}

export const ItemRow: React.FC<ItemRowProps> = ({ item, onStateChange, onReport, onSelect }) => {
  const [isNoteOpen, setIsNoteOpen] = useState(false)
  const [noteValue, setNoteValue] = useState(item.note || '')
  const [isReportOpen, setIsReportOpen] = useState(false)
  const [isUpdating, setIsUpdating] = useState(false)

  const kindMeta = getKindMetadata(item.kind)

  const handleStateChange = async (nextState: ProgressState) => {
    setIsUpdating(true)
    try {
      await onStateChange(nextState, noteValue)
    } finally {
      setIsUpdating(false)
    }
  }

  const handleSaveNote = async () => {
    setIsUpdating(true)
    try {
      await onStateChange(item.progress || 'to_do', noteValue)
      setIsNoteOpen(false)
    } finally {
      setIsUpdating(false)
    }
  }

  return (
    <div
      className={`rounded-2xl border bg-card p-4 shadow-xs transition-all hover:border-foreground/30 ${
        item.progress === 'done' ? 'bg-muted/10' : ''
      }`}
    >
      <div className="flex flex-col justify-between gap-3 sm:flex-row sm:items-center">
        {/* Left: Metadata & Titles */}
        <div className="flex min-w-0 flex-1 items-start gap-3">
          <div className="min-w-0 flex-1 space-y-1.5">
            <div className="flex flex-wrap items-center gap-2">
              <span className={`rounded-md border px-2 py-0.5 text-[11px] font-semibold ${kindMeta.color}`}>
                {kindMeta.shortLabel}
              </span>
              <button
                type="button"
                onClick={() => onSelect?.(item)}
                className="truncate text-left text-sm font-bold text-foreground hover:underline"
              >
                {item.canonical_label}
              </button>

              {/* Page Locator Badge */}
              {item.official_page && (
                <span className="rounded-md border bg-muted/50 px-2 py-0.5 font-mono text-xs text-muted-foreground">
                  {formatPageRange(item.official_page, item.solution_page)}
                </span>
              )}

              {/* Revised Since You Did It Badge */}
              {item.revised_since_done && (
                <span className="inline-flex animate-pulse items-center gap-1 rounded-full border border-amber-300 bg-amber-100 px-2 py-0.5 text-[10px] font-bold text-amber-900">
                  <Sparkles className="h-3 w-3 text-amber-600" />
                  Revised in latest edition
                </span>
              )}
            </div>

            {item.title && (
              <button
                type="button"
                onClick={() => onSelect?.(item)}
                className="line-clamp-1 cursor-pointer text-left text-xs text-muted-foreground hover:text-foreground"
              >
                {item.title}
              </button>
            )}

            {/* Note Preview if present and not expanded */}
            {!isNoteOpen && item.note && (
              <button
                type="button"
                onClick={() => setIsNoteOpen(true)}
                className="line-clamp-1 flex cursor-pointer items-center gap-1.5 pt-0.5 text-left text-xs text-muted-foreground/80 italic"
              >
                <MessageSquare className="h-3 w-3 shrink-0 text-muted-foreground" />
                <span>{item.note}</span>
              </button>
            )}
          </div>
        </div>

        {/* Right: Actions, Deep Link & State Toggle */}
        <div className="flex shrink-0 flex-wrap items-center gap-2 self-start sm:self-auto">
          {/* Official PDF Deep Link */}
          {item.deep_link && (
            <a
              href={item.deep_link}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex min-h-[44px] items-center gap-1 rounded-xl border px-2.5 py-1.5 text-xs font-semibold text-primary hover:bg-muted/60"
              title="Open Official Institute PDF directly at this page"
            >
              <span>Official PDF</span>
              <ExternalLink className="h-3.5 w-3.5" />
            </a>
          )}

          {/* Quick Note Toggle */}
          <button
            type="button"
            onClick={() => setIsNoteOpen(!isNoteOpen)}
            className={`flex min-h-[44px] min-w-[44px] items-center justify-center rounded-xl border p-2 text-xs transition-colors ${
              item.note
                ? 'border-primary/30 bg-primary/10 text-primary'
                : 'border-border text-muted-foreground hover:bg-muted/50'
            }`}
            title={item.note ? 'Edit your note' : 'Add private note'}
            aria-label="Toggle note field"
          >
            <MessageSquare className="h-4 w-4" />
          </button>

          {/* Report Button */}
          <button
            type="button"
            onClick={() => setIsReportOpen(true)}
            className="flex min-h-[44px] min-w-[44px] items-center justify-center rounded-xl border border-transparent p-2 text-xs text-muted-foreground hover:bg-muted/50 hover:text-foreground"
            title="Report broken link or mapping error"
            aria-label="Report issue"
          >
            <Flag className="h-3.5 w-3.5" />
          </button>

          {/* 3-Way State Toggle */}
          <StateToggle state={item.progress} onChange={handleStateChange} disabled={isUpdating} />
        </div>
      </div>

      {/* Expanded Note Field */}
      {isNoteOpen && (
        <div className="mt-3 space-y-2 border-t pt-3">
          <label htmlFor={`note-${item.id}`} className="text-xs font-semibold text-foreground">
            Private Notes & Reminders
          </label>
          <textarea
            id={`note-${item.id}`}
            rows={2}
            value={noteValue}
            onChange={(e) => setNoteValue(e.target.value)}
            placeholder="e.g. Revisit step 3 adjustment before exam, tricky deferred tax calc..."
            className="w-full resize-none rounded-xl border bg-background px-3 py-2 text-xs focus:ring-2 focus:ring-primary focus:outline-hidden"
          />
          <div className="flex items-center justify-end gap-2">
            <button
              type="button"
              onClick={() => setIsNoteOpen(false)}
              className="min-h-[36px] rounded-lg border px-3 py-1.5 text-xs font-medium hover:bg-muted"
            >
              Cancel
            </button>
            <button
              type="button"
              onClick={handleSaveNote}
              disabled={isUpdating}
              className="min-h-[36px] rounded-lg bg-foreground px-3 py-1.5 text-xs font-semibold text-background hover:opacity-90 disabled:opacity-50"
            >
              Save Note
            </button>
          </div>
        </div>
      )}

      {/* Report Modal */}
      <ReportModal
        itemId={item.id}
        itemLabel={item.canonical_label}
        isOpen={isReportOpen}
        onClose={() => setIsReportOpen(false)}
        onSubmit={async (payload) => {
          await onReport(payload)
        }}
      />
    </div>
  )
}
