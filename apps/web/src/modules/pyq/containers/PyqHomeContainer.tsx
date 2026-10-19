import {
  Alert,
  Badge,
  Button,
  ButtonLink,
  EmptyState,
  FileText,
  FilterChip,
  Input,
  Page,
  PageHeader,
  Search,
  SelectField,
  TableToolbar,
  toast,
} from '@artha/design-system'
import { Link, useNavigate } from '@tanstack/react-router'
import * as React from 'react'

import { useFeatureFlag } from '~/modules/observability'
import { useBootstrap } from '~/modules/personalization'

import { PapersTable, PapersTableSkeleton } from '../components/PapersTable'
import { listPapers, startPaperPractice } from '../lib/api'
import { termLabel } from '../lib/labels'
import type { PyqPaperCard, PyqSearch } from '../lib/types'

interface PyqHomeContainerProps {
  search?: PyqSearch
}

const TERMS = [
  { value: 'all', label: 'All Terms' },
  { value: 'dec_2023', label: 'December 2023' },
  { value: 'june_2023', label: 'June 2023' },
  { value: 'dec_2022', label: 'December 2022' },
  { value: 'june_2022', label: 'June 2022' },
]

export function PyqHomeContainer({ search = {} }: PyqHomeContainerProps) {
  const enabled = useFeatureFlag('pyq_bank', { strict: true })
  const { data: bootstrapData } = useBootstrap()
  const navigate = useNavigate()

  const enrolledCourse = bootstrapData?.course?.course.code
  const enrolledCourseName = bootstrapData?.course?.course.name ?? 'CMA'
  const enrolledLevel = bootstrapData?.course?.level.code
  const enrolledLevelName = bootstrapData?.course?.level.name ?? 'Final'

  const [loading, setLoading] = React.useState(true)
  const [papers, setPapers] = React.useState<PyqPaperCard[]>([])
  const [termFilter, setTermFilter] = React.useState(search.term || 'all')
  const [query, setQuery] = React.useState(search.q || '')
  const [startingPaperId, setStartingPaperId] = React.useState<string | null>(null)
  const [error, setError] = React.useState<string | null>(null)

  const fetchPapers = React.useCallback(async () => {
    if (!enabled) return
    setLoading(true)
    setError(null)
    try {
      const items = await listPapers({
        course: enrolledCourse,
        level: enrolledLevel,
        term: termFilter !== 'all' ? termFilter : undefined,
      })
      setPapers(items)
    } catch {
      setError('Unable to load past papers right now. Please try again.')
    } finally {
      setLoading(false)
    }
  }, [enabled, enrolledCourse, enrolledLevel, termFilter])

  React.useEffect(() => {
    fetchPapers()
  }, [fetchPapers])

  const handleStartPractice = async (paperId: string) => {
    setStartingPaperId(paperId)
    try {
      const res = await startPaperPractice(paperId, { mode: 'untimed' })
      toast.success('Paper practice session ready!')
      navigate({
        to: '/app/practice/session/$id',
        params: { id: res.session_id },
      })
    } catch {
      toast.error('Failed to create practice session from paper.')
    } finally {
      setStartingPaperId(null)
    }
  }

  if (!enabled) {
    return (
      <Page width="form">
        <Alert variant="info">
          The Previous Year Questions (PYQ) bank is currently under rollout and not yet available.
        </Alert>
      </Page>
    )
  }

  const filteredPapers = papers.filter((p) => {
    if (!query) return true
    const q = query.toLowerCase()
    return (
      p.title.toLowerCase().includes(q) ||
      p.subject_key.toLowerCase().includes(q) ||
      p.term_code.toLowerCase().includes(q) ||
      p.paper_code.toLowerCase().includes(q)
    )
  })

  const institution = enrolledCourse === 'ca' ? 'ICAI' : enrolledCourse === 'cs' ? 'ICSI' : 'ICMAI'

  const resetFilters = () => {
    setTermFilter('all')
    setQuery('')
  }

  const activeFilters: Array<{ key: string; label: string; onRemove: () => void }> = []
  if (query) activeFilters.push({ key: 'q', label: `Search: "${query}"`, onRemove: () => setQuery('') })
  if (termFilter !== 'all') {
    const label = TERMS.find((t) => t.value === termFilter)?.label ?? termLabel(termFilter)
    activeFilters.push({ key: 'term', label: `Term: ${label}`, onRemove: () => setTermFilter('all') })
  }

  return (
    <Page>
      <PageHeader
        title={
          <span className="inline-flex items-center gap-2">
            Past Papers & PYQ Bank
            <Badge className="font-mono">
              {enrolledCourseName} • {enrolledLevelName}
            </Badge>
          </span>
        }
        description={`Browse, simulate and practise original ${institution} ${enrolledCourseName} ${enrolledLevelName} exam papers with syllabus mappings and suggested solutions.`}
        actions={
          <>
            <ButtonLink asChild variant="outline" size="sm">
              <Link to="/app/questions">Question Bank</Link>
            </ButtonLink>
            <ButtonLink asChild>
              <Link to="/app/practice/new">Custom Practice</Link>
            </ButtonLink>
          </>
        }
      />

      <div className="space-y-2">
        <TableToolbar>
          <div className="relative w-full sm:w-64">
            <Search
              aria-hidden
              className="pointer-events-none absolute top-1/2 left-2.5 size-3.5 -translate-y-1/2 text-muted-foreground"
            />
            <Input
              id="pyq-query"
              type="search"
              aria-label="Search by subject or paper code"
              placeholder="Search subject or paper code"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              className="w-full pl-8 sm:w-64"
            />
          </div>
          <SelectField
            id="pyq-term"
            aria-label="Exam term"
            value={termFilter}
            onValueChange={setTermFilter}
            options={TERMS}
            className="w-44"
          />
          {!loading && !error && (
            <p aria-live="polite" className="text-xs text-muted-foreground tabular-nums sm:ml-auto">
              Showing {filteredPapers.length}
            </p>
          )}
        </TableToolbar>

        {activeFilters.length > 0 && (
          <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
            <span className="text-xs text-muted-foreground">Active filters:</span>
            {activeFilters.map((chip) => (
              <FilterChip key={chip.key} removeLabel={`Remove ${chip.label}`} onRemove={chip.onRemove}>
                {chip.label}
              </FilterChip>
            ))}
            <Button type="button" variant="ghost" size="xs" onClick={resetFilters}>
              Clear all
            </Button>
          </div>
        )}
      </div>

      {error && <Alert variant="error">{error}</Alert>}

      {loading ? (
        <PapersTableSkeleton />
      ) : filteredPapers.length === 0 ? (
        <EmptyState
          icon={<FileText aria-hidden className="size-6" />}
          title="No past papers match your filter"
          description="Try selecting a different level or term, or clear your search query."
          action={
            <Button variant="outline" size="sm" onClick={resetFilters}>
              Reset Filters
            </Button>
          }
        />
      ) : (
        <PapersTable papers={filteredPapers} onStartPractice={handleStartPractice} startingPaperId={startingPaperId} />
      )}
    </Page>
  )
}
