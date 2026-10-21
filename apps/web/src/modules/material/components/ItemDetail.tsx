import { ArrowLeft, BookOpen, ExternalLink, Flag, ShieldCheck, Sparkles } from '@artha/design-system'
import React, { useState } from 'react'

import { getKindMetadata, getRightsDescription } from '../lib/labels'
import { formatPageRange } from '../lib/locator'
import type { MaterialItem, MaterialReportPayload, ProgressState } from '../lib/types'
import { ReportModal } from './ReportModal'
import { StateToggle } from './StateToggle'

interface ItemDetailProps {
  item: MaterialItem
  onStateChange: (state: ProgressState, note?: string) => Promise<void>
  onReport: (payload: MaterialReportPayload) => Promise<void>
  onBack: () => void
}

export const ItemDetail: React.FC<ItemDetailProps> = ({ item, onStateChange, onReport, onBack }) => {
  const [noteValue, setNoteValue] = useState(item.note || '')
  const [isReportOpen, setIsReportOpen] = useState(false)
  const [isUpdating, setIsUpdating] = useState(false)
  const [noteSaved, setNoteSaved] = useState(false)

  const kindMeta = getKindMetadata(item.kind)
  const rightsMeta = getRightsDescription(item.rights_level)

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
      setNoteSaved(true)
      setTimeout(() => setNoteSaved(false), 2000)
    } finally {
      setIsUpdating(false)
    }
  }

  return (
    <div className="mx-auto max-w-4xl space-y-6 p-4 sm:p-8">
      {/* Back button */}
      <div>
        <button
          type="button"
          onClick={onBack}
          className="inline-flex min-h-[44px] items-center gap-2 text-sm text-muted-foreground hover:text-foreground"
        >
          <ArrowLeft className="h-4 w-4" />
          Back to Chapter Items
        </button>
      </div>

      {/* Main Item Card */}
      <div className="space-y-6 rounded-3xl border bg-card p-6 shadow-xs sm:p-8">
        {/* Header */}
        <div className="flex flex-col justify-between gap-4 border-b pb-6 sm:flex-row sm:items-start">
          <div className="space-y-2">
            <div className="flex flex-wrap items-center gap-2">
              <span className={`rounded-md border px-2.5 py-1 text-xs font-semibold ${kindMeta.color}`}>
                {kindMeta.label}
              </span>
              <span className="rounded-md border bg-muted/60 px-2 py-0.5 font-mono text-xs text-muted-foreground">
                {formatPageRange(item.official_page, item.solution_page)}
              </span>
              {item.revised_since_done && (
                <span className="inline-flex items-center gap-1 rounded-full border border-amber-300 bg-amber-100 px-2.5 py-1 text-xs font-bold text-amber-900">
                  <Sparkles className="h-3.5 w-3.5 text-amber-600" />
                  Revised in latest edition
                </span>
              )}
            </div>

            <h1 className="text-2xl font-bold tracking-tight text-foreground">{item.canonical_label}</h1>
            {item.title && <p className="text-base text-muted-foreground">{item.title}</p>}
          </div>

          <div className="flex shrink-0 items-center gap-3 self-start sm:self-auto">
            <button
              type="button"
              onClick={() => setIsReportOpen(true)}
              className="flex min-h-[44px] min-w-[44px] items-center justify-center rounded-xl border p-2 text-muted-foreground hover:bg-muted/50 hover:text-foreground"
              title="Report issue with this item"
              aria-label="Report issue"
            >
              <Flag className="h-4 w-4" />
            </button>
            <StateToggle state={item.progress} onChange={handleStateChange} disabled={isUpdating} />
          </div>
        </div>

        {/* Content Section based on Rights Level */}
        <div className="space-y-4">
          {item.content_html ? (
            <div
              className="prose prose-sm sm:prose-base max-w-none rounded-2xl border bg-muted/10 p-6 leading-relaxed text-foreground"
              dangerouslySetInnerHTML={{ __html: item.content_html }}
            />
          ) : item.content_markdown ? (
            <div className="rounded-2xl border bg-muted/10 p-6 font-sans text-sm leading-relaxed whitespace-pre-wrap">
              {item.content_markdown}
            </div>
          ) : (
            /* L1 / External Link Banner */
            <div className="space-y-4 rounded-2xl border border-dashed bg-muted/20 p-6 text-center sm:p-8">
              <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-2xl bg-primary/10 text-primary">
                <BookOpen className="h-6 w-6" />
              </div>
              <div className="mx-auto max-w-md space-y-1">
                <h3 className="text-base font-semibold text-foreground">View in Official Institute Study Material</h3>
                <p className="text-xs leading-relaxed text-muted-foreground">
                  To ensure 100% compliance with Institute copyright and statutory provisions, Artha provides a direct
                  deep link to this exact page in the official publication.
                </p>
              </div>

              {item.deep_link ? (
                <a
                  href={item.deep_link}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex min-h-[44px] items-center gap-2 rounded-xl bg-primary px-5 py-2.5 text-sm font-semibold text-primary-foreground hover:opacity-90"
                >
                  <span>Open Official PDF at {formatPageRange(item.official_page, item.solution_page)}</span>
                  <ExternalLink className="h-4 w-4" />
                </a>
              ) : (
                <div className="text-xs text-muted-foreground">Official PDF URL not yet mapped for this edition.</div>
              )}
            </div>
          )}
        </div>

        {/* Rights & Licensing Info Pill */}
        <div className="flex items-center gap-3 rounded-2xl border bg-muted/40 p-3 text-xs text-muted-foreground">
          <ShieldCheck className="h-4 w-4 shrink-0 text-emerald-600" />
          <div className="flex-1">
            <span className="font-semibold text-foreground">{rightsMeta.title}: </span>
            <span>{rightsMeta.description}</span>
          </div>
        </div>

        {/* Student Private Notes Section */}
        <div className="space-y-3 border-t pt-6">
          <div className="flex items-center justify-between">
            <label htmlFor="detail-notes" className="text-sm font-semibold text-foreground">
              Your Personal Notes & Adjustments
            </label>
            {noteSaved && <span className="text-xs font-semibold text-emerald-600">Saved!</span>}
          </div>
          <textarea
            id="detail-notes"
            rows={4}
            value={noteValue}
            onChange={(e) => setNoteValue(e.target.value)}
            placeholder="Key concepts to remember, difficult journal entries, exam-day caveats..."
            className="w-full resize-y rounded-2xl border bg-background px-4 py-3 text-sm focus:ring-2 focus:ring-primary focus:outline-hidden"
          />
          <div className="flex justify-end">
            <button
              type="button"
              onClick={handleSaveNote}
              disabled={isUpdating}
              className="min-h-[44px] rounded-xl bg-foreground px-5 py-2.5 text-xs font-semibold text-background hover:opacity-90 disabled:opacity-50"
            >
              Save Note
            </button>
          </div>
        </div>
      </div>

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
