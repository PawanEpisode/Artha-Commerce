import { BookOpen, Building2, ChevronRight, Search, Settings } from '@artha/design-system'
import React, { useState } from 'react'

import { useWorks } from '../hooks/useWorks'
import type { Work } from '../lib/types'

interface MaterialHubContainerProps {
  onSelectWork: (workKey: string) => void
  onOpenRegistry?: () => void
}

export const MaterialHubContainer: React.FC<MaterialHubContainerProps> = ({ onSelectWork, onOpenRegistry }) => {
  const { works, filters, setFilters, isLoading, error } = useWorks()
  const [searchInput, setSearchInput] = useState(filters.q || '')

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    setFilters({ ...filters, q: searchInput })
  }

  return (
    <div className="mx-auto max-w-6xl space-y-8 p-4 sm:p-8">
      {/* Top Banner */}
      <div className="flex flex-col justify-between gap-4 border-b pb-6 sm:flex-row sm:items-center">
        <div>
          <div className="mb-3 inline-flex items-center gap-2 rounded-full bg-primary/10 px-3 py-1 text-xs font-semibold text-primary">
            <BookOpen className="h-3.5 w-3.5" />
            <span>F-12 Institute Study Material</span>
          </div>
          <h1 className="text-3xl font-extrabold tracking-tight text-foreground">Study Material & Module Checklists</h1>
          <p className="mt-1 max-w-2xl text-sm text-muted-foreground">
            Official institute study material mapped chapter-by-chapter with illustrations, practical exercises, and
            deep-linked PDF references.
          </p>
        </div>

        {onOpenRegistry && (
          <button
            type="button"
            onClick={onOpenRegistry}
            className="inline-flex min-h-[44px] items-center gap-2 self-start rounded-xl border px-4 py-2 text-xs font-semibold hover:bg-muted sm:self-auto"
          >
            <Settings className="h-4 w-4 text-muted-foreground" />
            <span>Institute Settings</span>
          </button>
        )}
      </div>

      {/* Search and Filters Strip */}
      <div className="flex flex-col items-stretch gap-3 sm:flex-row sm:items-center">
        <form onSubmit={handleSearchSubmit} className="relative flex-1">
          <Search className="pointer-events-none absolute top-1/2 left-3.5 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <input
            type="search"
            value={searchInput}
            onChange={(e) => setSearchInput(e.target.value)}
            placeholder="Search by subject, chapter title, or book..."
            className="min-h-[44px] w-full rounded-2xl border bg-background py-2 pr-4 pl-10 text-sm focus:ring-2 focus:ring-primary focus:outline-hidden"
          />
        </form>

        <div className="flex items-center gap-2">
          <select
            value={filters.course || ''}
            onChange={(e) => setFilters({ ...filters, course: e.target.value || undefined })}
            aria-label="Filter by course"
            className="min-h-[44px] rounded-xl border bg-background px-3 py-2 text-xs font-medium focus:ring-2 focus:ring-primary focus:outline-hidden"
          >
            <option value="">All Courses</option>
            <option value="ca">Chartered Accountancy (CA)</option>
            <option value="cma">Cost & Management (CMA)</option>
            <option value="cs">Company Secretary (CS)</option>
          </select>

          <select
            value={filters.level || ''}
            onChange={(e) => setFilters({ ...filters, level: e.target.value || undefined })}
            aria-label="Filter by level"
            className="min-h-[44px] rounded-xl border bg-background px-3 py-2 text-xs font-medium focus:ring-2 focus:ring-primary focus:outline-hidden"
          >
            <option value="">All Levels</option>
            <option value="foundation">Foundation</option>
            <option value="intermediate">Intermediate</option>
            <option value="final">Final</option>
          </select>
        </div>
      </div>

      {/* Content */}
      {isLoading ? (
        <div className="grid animate-pulse grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
          {[1, 2, 3, 4, 5, 6].map((n) => (
            <div key={n} className="h-44 rounded-3xl border bg-muted/40" />
          ))}
        </div>
      ) : error ? (
        <div className="rounded-3xl border border-rose-200 bg-rose-50/50 p-8 text-center text-sm text-rose-800">
          Failed to load study materials. Please check your connection.
        </div>
      ) : works.length === 0 ? (
        <div className="space-y-2 rounded-3xl border bg-muted/10 p-12 text-center text-sm text-muted-foreground">
          <BookOpen className="mx-auto h-8 w-8 text-muted-foreground/60" />
          <p className="font-semibold text-foreground">No study material found</p>
          <p className="text-xs">Try selecting a different course or clearing your search filter.</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-5 md:grid-cols-2 lg:grid-cols-3">
          {works.map((work) => (
            <WorkCard key={work.id} work={work} onSelect={() => onSelectWork(work.work_key || work.slug || work.id)} />
          ))}
        </div>
      )}
    </div>
  )
}

const WorkCard: React.FC<{ work: Work; onSelect: () => void }> = ({ work, onSelect }) => {
  const editionLabel = work.current_edition?.label || work.edition?.label
  const chapterCount = work.chapters_count ?? work.item_count ?? 0

  return (
    <button
      type="button"
      onClick={onSelect}
      className="group flex w-full cursor-pointer flex-col justify-between gap-4 rounded-3xl border bg-card p-5 text-left transition-all hover:border-foreground/40 hover:shadow-md sm:p-6"
    >
      <div className="space-y-3">
        <div className="flex items-center justify-between gap-2">
          <span className="rounded-full bg-primary/10 px-2.5 py-0.5 text-[11px] font-bold tracking-wide text-primary uppercase">
            {work.course || 'CMA'} • {work.level || 'Final'}
          </span>
          {editionLabel && (
            <span className="rounded-md border bg-muted/50 px-2 py-0.5 font-mono text-xs text-muted-foreground">
              {editionLabel}
            </span>
          )}
        </div>

        <div className="space-y-1">
          <h2 className="text-base leading-snug font-bold text-foreground transition-colors group-hover:text-primary">
            {work.title}
          </h2>
          <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
            <Building2 className="h-3.5 w-3.5" />
            <span>{work.provider?.name || 'ICMAI'}</span>
          </div>
        </div>
      </div>

      <div className="flex items-center justify-between border-t pt-3 text-xs text-muted-foreground">
        <span>{chapterCount} Chapters</span>
        <div className="flex items-center gap-1 font-semibold text-primary transition-transform group-hover:translate-x-0.5">
          <span>Open Book</span>
          <ChevronRight className="h-4 w-4" />
        </div>
      </div>
    </button>
  )
}
