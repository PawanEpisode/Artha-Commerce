import { ArrowLeft, BookOpen, ChevronRight, GitCompare, Layers } from '@artha/design-system'
import React, { useState } from 'react'

import { PdfViewerModal } from '../../mocktest/components/PdfViewerModal'
import { EditionBanner } from '../components/EditionBanner'
import { useWorkDetail } from '../hooks/useWorkDetail'
import type { UnitDetail } from '../lib/types'

interface WorkContainerProps {
  workKey: string
  onSelectChapter: (workKey: string, chapterKey: string) => void
  onCompareEditions: (workKey: string, fromEdition: string, toEdition: string) => void
  onBack: () => void
}

export const WorkContainer: React.FC<WorkContainerProps> = ({
  workKey,
  onSelectChapter,
  onCompareEditions,
  onBack,
}) => {
  const { work, userEdition, isLoading, error, selectEdition, dismissBanner } = useWorkDetail(workKey)

  const [selectedEditionId, setSelectedEditionId] = useState<string | null>(null)
  const [isBannerDismissed, setIsBannerDismissed] = useState(false)
  const [isReaderOpen, setIsReaderOpen] = useState(false)

  if (isLoading) {
    return (
      <div className="mx-auto max-w-5xl animate-pulse space-y-6 p-4 sm:p-8">
        <div className="h-24 rounded-3xl bg-muted/40" />
        <div className="space-y-4">
          <div className="h-32 rounded-2xl bg-muted/30" />
          <div className="h-32 rounded-2xl bg-muted/30" />
        </div>
      </div>
    )
  }

  if (error || !work) {
    return (
      <div className="mx-auto max-w-md space-y-4 p-8 text-center">
        <div className="rounded-2xl border border-rose-200 bg-rose-50 p-4 text-sm text-rose-700">
          Failed to load study material book.
        </div>
        <button
          type="button"
          onClick={onBack}
          className="min-h-[44px] rounded-xl border px-4 py-2 text-sm font-semibold"
        >
          Back to Library
        </button>
      </div>
    )
  }

  const currentPublishedEdition = work.current_edition
  const activeEditionId =
    selectedEditionId || userEdition?.edition_id || currentPublishedEdition?.id || work.editions?.[0]?.id

  const activeEditionDetail = work.editions?.find((e) => e.id === activeEditionId) || work.editions?.[0]
  const isStale =
    currentPublishedEdition && activeEditionDetail && activeEditionDetail.id !== currentPublishedEdition.id

  const targetWorkKey = work.work_key || work.slug || work.id
  const bookPdfUrl =
    activeEditionDetail?.source_url ||
    activeEditionDetail?.pdf_url ||
    currentPublishedEdition?.source_url ||
    currentPublishedEdition?.pdf_url ||
    (work.edition as { source_url?: string | null })?.source_url

  const handleDismissBanner = () => {
    setIsBannerDismissed(true)
    dismissBanner()
  }

  return (
    <div className="mx-auto max-w-5xl space-y-6 p-4 sm:p-8">
      {/* Back button */}
      <div>
        <button
          type="button"
          onClick={onBack}
          className="inline-flex min-h-[44px] items-center gap-2 text-sm text-muted-foreground hover:text-foreground"
        >
          <ArrowLeft className="h-4 w-4" />
          Back to Study Material Hub
        </button>
      </div>

      {/* Book Hero */}
      <div className="space-y-6 rounded-3xl border bg-card p-6 shadow-xs sm:p-8">
        <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-start">
          <div className="space-y-2">
            <div className="flex flex-wrap items-center gap-2">
              <span className="rounded-full bg-primary/10 px-2.5 py-0.5 text-[11px] font-bold text-primary uppercase">
                {work.course} • {work.level}
              </span>
              <span className="text-xs font-semibold text-muted-foreground">{work.provider?.name}</span>
            </div>
            <h1 className="text-2xl font-extrabold tracking-tight text-foreground sm:text-3xl">{work.title}</h1>
          </div>

          {/* Edition Selector & Compare Button */}
          <div className="flex shrink-0 flex-wrap items-center gap-2 self-start sm:self-auto">
            {work.editions && work.editions.length > 1 && (
              <select
                value={activeEditionDetail?.id || ''}
                onChange={(e) => {
                  const targetId = e.target.value
                  setSelectedEditionId(targetId)
                  const targetEd = work.editions.find((ed) => ed.id === targetId)
                  if (targetEd) {
                    selectEdition(targetEd.edition_key).catch(() => {})
                  }
                }}
                aria-label="Select edition"
                className="min-h-[44px] rounded-xl border bg-background px-3 py-2 text-xs font-semibold focus:ring-2 focus:ring-primary focus:outline-hidden"
              >
                {work.editions.map((ed) => (
                  <option key={ed.id} value={ed.id}>
                    {ed.label} {ed.is_current ? '(Current)' : ''}
                  </option>
                ))}
              </select>
            )}

            {bookPdfUrl && (
              <button
                type="button"
                onClick={() => setIsReaderOpen(true)}
                className="inline-flex min-h-[44px] items-center gap-1.5 rounded-xl bg-primary px-4 py-2 text-xs font-bold text-primary-foreground shadow-xs transition-colors hover:bg-primary/90"
              >
                <BookOpen className="h-4 w-4" />
                <span>Read Book (PDF Reader)</span>
              </button>
            )}

            {work.editions && work.editions.length > 1 && (
              <button
                type="button"
                onClick={() => {
                  if (work.editions.length >= 2) {
                    onCompareEditions(targetWorkKey, work.editions[1].edition_key, work.editions[0].edition_key)
                  }
                }}
                className="inline-flex min-h-[44px] items-center gap-1.5 rounded-xl border px-3 py-2 text-xs font-semibold hover:bg-muted"
              >
                <GitCompare className="h-4 w-4 text-muted-foreground" />
                <span>Compare Editions</span>
              </button>
            )}
          </div>
        </div>

        {/* Stale Edition Alert Banner */}
        {isStale && !isBannerDismissed && currentPublishedEdition && activeEditionDetail && (
          <EditionBanner
            currentEditionLabel={activeEditionDetail.label}
            latestEditionLabel={currentPublishedEdition.label}
            onCompare={() =>
              onCompareEditions(targetWorkKey, activeEditionDetail.edition_key, currentPublishedEdition.edition_key)
            }
            onSwitchLatest={() => {
              setSelectedEditionId(currentPublishedEdition.id)
              selectEdition(currentPublishedEdition.edition_key).catch(() => {})
            }}
            onDismiss={handleDismissBanner}
          />
        )}
      </div>

      {/* Units & Chapters List */}
      <div className="space-y-6">
        <div className="flex items-center justify-between">
          <h2 className="flex items-center gap-2 text-lg font-bold text-foreground">
            <Layers className="h-5 w-5 text-primary" />
            <span>Modules & Chapters ({activeEditionDetail?.label || 'Current'})</span>
          </h2>
        </div>

        {(() => {
          const activeUnits = activeEditionDetail?.units || (work.edition as { units?: UnitDetail[] })?.units || []
          const directChapters =
            (
              work as {
                chapters?: Array<{ chapter_key: string; chapter_id?: string; summary?: { total_items?: number } }>
              }
            ).chapters || []

          if (activeUnits.length > 0) {
            return (
              <div className="space-y-4">
                {activeUnits.map((unit) => (
                  <div key={unit.id} className="space-y-3 rounded-2xl border bg-card p-5">
                    <div className="flex items-center gap-2 text-xs font-bold tracking-wider text-muted-foreground uppercase">
                      <span>Unit {unit.unit_number}</span>
                      <span>•</span>
                      <span>{unit.title}</span>
                    </div>

                    <div className="divide-y divide-border/60">
                      {unit.chapters.map((chapter) => (
                        <button
                          type="button"
                          key={chapter.id}
                          onClick={() => onSelectChapter(targetWorkKey, chapter.chapter_key)}
                          className="group -mx-3 flex w-full cursor-pointer items-center justify-between gap-3 rounded-xl px-3 py-3 text-left transition-colors hover:bg-muted/30"
                        >
                          <div className="space-y-0.5">
                            <div className="text-sm font-semibold text-foreground transition-colors group-hover:text-primary">
                              {chapter.title}
                            </div>
                            <div className="text-xs text-muted-foreground">
                              {chapter.items_count} official items (illustrations & exercises)
                            </div>
                          </div>

                          <div className="flex shrink-0 items-center gap-2">
                            <span className="text-xs font-semibold text-muted-foreground group-hover:text-primary">
                              Open Checklist
                            </span>
                            <ChevronRight className="h-4 w-4 text-muted-foreground transition-transform group-hover:translate-x-0.5" />
                          </div>
                        </button>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            )
          }

          if (directChapters.length > 0) {
            return (
              <div className="space-y-3 rounded-2xl border bg-card p-5">
                <div className="divide-y divide-border/60">
                  {directChapters.map((chapter) => (
                    <button
                      type="button"
                      key={chapter.chapter_id || chapter.chapter_key}
                      onClick={() => onSelectChapter(targetWorkKey, chapter.chapter_key)}
                      className="group -mx-3 flex w-full cursor-pointer items-center justify-between gap-3 rounded-xl px-3 py-3 text-left transition-colors hover:bg-muted/30"
                    >
                      <div className="space-y-0.5">
                        <div className="text-sm font-semibold text-foreground transition-colors group-hover:text-primary">
                          {chapter.chapter_key.replace(/-/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase())}
                        </div>
                        <div className="text-xs text-muted-foreground">
                          {chapter.summary?.total_items ?? 0} official items (illustrations & exercises)
                        </div>
                      </div>

                      <div className="flex shrink-0 items-center gap-2">
                        <span className="text-xs font-semibold text-muted-foreground group-hover:text-primary">
                          Open Checklist
                        </span>
                        <ChevronRight className="h-4 w-4 text-muted-foreground transition-transform group-hover:translate-x-0.5" />
                      </div>
                    </button>
                  ))}
                </div>
              </div>
            )
          }

          return (
            <div className="rounded-3xl border bg-muted/10 p-12 text-center text-sm text-muted-foreground">
              No units or chapters found for this edition.
            </div>
          )
        })()}
      </div>

      {bookPdfUrl && (
        <PdfViewerModal
          isOpen={isReaderOpen}
          title={work.title}
          pdfUrl={bookPdfUrl}
          subtitle={`${work.provider?.name || 'ICMAI'} Study Material Book · ${activeEditionDetail?.label || 'Official Edition'}`}
          onClose={() => setIsReaderOpen(false)}
        />
      )}
    </div>
  )
}
