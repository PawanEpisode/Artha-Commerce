import {
  Alert,
  Badge,
  Button,
  ButtonLink,
  Card,
  EmptyState,
  FileText,
  Input,
  Label,
  SelectField,
  Skeleton,
  toast,
} from '@artha/design-system'
import { Link, useNavigate } from '@tanstack/react-router'
import * as React from 'react'

import { useFeatureFlag } from '~/modules/observability'

import { PaperCard } from '../components/PaperCard'
import { listPapers, startPaperPractice } from '../lib/api'
import type { PyqPaperCard, PyqSearch } from '../lib/types'

interface PyqHomeContainerProps {
  search?: PyqSearch
}

const CMA_LEVELS = [
  { value: 'all', label: 'All Levels' },
  { value: 'cma_intermediate', label: 'CMA Intermediate' },
  { value: 'cma_final', label: 'CMA Final' },
]

const TERMS = [
  { value: 'all', label: 'All Terms' },
  { value: 'dec_2023', label: 'December 2023' },
  { value: 'june_2023', label: 'June 2023' },
  { value: 'dec_2022', label: 'December 2022' },
  { value: 'june_2022', label: 'June 2022' },
]

export function PyqHomeContainer({ search = {} }: PyqHomeContainerProps) {
  const enabled = useFeatureFlag('pyq_bank', { strict: true })
  const navigate = useNavigate()

  const [loading, setLoading] = React.useState(true)
  const [papers, setPapers] = React.useState<PyqPaperCard[]>([])
  const [levelFilter, setLevelFilter] = React.useState(search.level || 'all')
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
        level: levelFilter !== 'all' ? levelFilter : undefined,
        term: termFilter !== 'all' ? termFilter : undefined,
      })
      setPapers(items)
    } catch {
      setError('Unable to load past papers right now. Please try again.')
    } finally {
      setLoading(false)
    }
  }, [enabled, levelFilter, termFilter])

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
      <div className="mx-auto max-w-4xl px-4 py-12">
        <Alert variant="info">
          The Previous Year Questions (PYQ) bank is currently under rollout and not yet available.
        </Alert>
      </div>
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

  return (
    <div className="mx-auto max-w-6xl space-y-6 px-4 py-8">
      {/* Header */}
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-2xl font-bold tracking-tight text-foreground sm:text-3xl">Past Papers & PYQ Bank</h1>
            <Badge variant="default" className="font-mono text-xs">
              CMA 2022
            </Badge>
          </div>
          <p className="mt-1 text-sm text-muted-foreground">
            Browse, simulate and practise original ICMAI exam papers with syllabus mappings and suggested solutions.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <ButtonLink asChild variant="outline" size="sm">
            <Link to="/app/practice/new">Custom Practice</Link>
          </ButtonLink>
          <ButtonLink asChild variant="outline" size="sm">
            <Link to="/app/questions">Question Bank</Link>
          </ButtonLink>
        </div>
      </div>

      {/* Filter Toolbar */}
      <Card className="p-4">
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
          <div>
            <Label htmlFor="pyq-query" className="mb-1 block text-xs font-medium text-muted-foreground">
              Search by subject or paper code
            </Label>
            <Input
              id="pyq-query"
              placeholder="e.g. Direct Tax, Law, Costing..."
              value={query}
              onChange={(e) => setQuery(e.target.value)}
            />
          </div>

          <div>
            <Label htmlFor="pyq-level" className="mb-1 block text-xs font-medium text-muted-foreground">
              Exam Level
            </Label>
            <SelectField id="pyq-level" value={levelFilter} onValueChange={setLevelFilter} options={CMA_LEVELS} />
          </div>

          <div>
            <Label htmlFor="pyq-term" className="mb-1 block text-xs font-medium text-muted-foreground">
              Exam Term
            </Label>
            <SelectField id="pyq-term" value={termFilter} onValueChange={setTermFilter} options={TERMS} />
          </div>
        </div>
      </Card>

      {/* Content State */}
      {error && <Alert variant="error">{error}</Alert>}

      {loading ? (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {[...Array(6)].map((_, i) => (
            <Card key={i} className="space-y-4 p-5">
              <Skeleton className="h-6 w-3/4" />
              <Skeleton className="h-4 w-1/2" />
              <div className="flex justify-between border-t border-border pt-4">
                <Skeleton className="h-8 w-24" />
                <Skeleton className="h-8 w-28" />
              </div>
            </Card>
          ))}
        </div>
      ) : filteredPapers.length === 0 ? (
        <EmptyState
          icon={<FileText aria-hidden className="size-6" />}
          title="No past papers match your filter"
          description="Try selecting a different level or term, or clear your search query."
          action={
            <Button
              variant="outline"
              size="sm"
              onClick={() => {
                setLevelFilter('all')
                setTermFilter('all')
                setQuery('')
              }}
            >
              Reset Filters
            </Button>
          }
        />
      ) : (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {filteredPapers.map((paper) => (
            <PaperCard
              key={paper.id}
              paper={paper}
              onStartPractice={handleStartPractice}
              isStarting={startingPaperId === paper.id}
            />
          ))}
        </div>
      )}
    </div>
  )
}
