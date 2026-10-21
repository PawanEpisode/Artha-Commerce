import React, { useState } from 'react'

import { PaperCard } from '../components/PaperCard'
import { usePapers } from '../hooks/usePapers'

interface MockCatalogContainerProps {
  onSelectPaper: (paperId: string) => void
}

export const MockCatalogContainer: React.FC<MockCatalogContainerProps> = ({ onSelectPaper }) => {
  const [selectedKind, setSelectedKind] = useState<string>('all')
  const { papers, isLoading, error } = usePapers(selectedKind !== 'all' ? { kind: selectedKind } : undefined)

  return (
    <div className="mx-auto max-w-6xl space-y-8 p-4 sm:p-8">
      {/* Header */}
      <div className="space-y-2">
        <h1 className="text-3xl font-black tracking-tight text-foreground sm:text-4xl">Mock Tests & MTP</h1>
        <p className="max-w-2xl text-sm text-muted-foreground sm:text-base">
          Exam-condition test papers, official Institute MTP series, and blueprint-matched full mocks with strict timers
          and cohort percentiles.
        </p>
      </div>

      {/* Filter Tabs */}
      <div className="flex items-center gap-2 overflow-x-auto border-b border-border pb-3">
        {[
          { key: 'all', label: 'All Papers' },
          { key: 'mtp', label: 'Institute MTP Series' },
          { key: 'mock', label: 'Full Mock Tests' },
        ].map((tab) => (
          <button
            key={tab.key}
            type="button"
            onClick={() => setSelectedKind(tab.key)}
            className={`min-h-[44px] rounded-xl px-4 py-2 text-sm font-semibold transition-all ${
              selectedKind === tab.key
                ? 'bg-primary text-primary-foreground shadow-xs'
                : 'bg-muted/40 text-muted-foreground hover:bg-muted hover:text-foreground'
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Content */}
      {isLoading ? (
        <div className="grid animate-pulse grid-cols-1 gap-6 md:grid-cols-2 lg:grid-cols-3">
          {[1, 2, 3, 4, 5, 6].map((i) => (
            <div key={i} className="h-48 rounded-2xl border bg-muted/40" />
          ))}
        </div>
      ) : error ? (
        <div className="rounded-2xl border border-rose-200 bg-rose-50 p-6 text-sm text-rose-700">
          Failed to load mock tests. Please refresh or try again later.
        </div>
      ) : papers.length === 0 ? (
        <div className="space-y-3 rounded-3xl border border-dashed bg-muted/20 p-12 text-center">
          <div className="text-4xl">📝</div>
          <h3 className="text-lg font-bold text-foreground">No test papers published yet</h3>
          <p className="mx-auto max-w-md text-sm text-muted-foreground">
            Test series and MTP papers for your registered course and attempt will be released here.
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-6 md:grid-cols-2 lg:grid-cols-3">
          {papers.map((paper) => (
            <PaperCard key={paper.id} paper={paper} onSelect={onSelectPaper} />
          ))}
        </div>
      )}
    </div>
  )
}
