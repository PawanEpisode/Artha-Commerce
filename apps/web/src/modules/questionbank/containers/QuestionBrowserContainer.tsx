import {
  Alert,
  Button,
  EmptyState,
  FilterChip,
  Input,
  Page,
  PageHeader,
  Search,
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
  TableToolbar,
} from '@artha/design-system'
import { Link, useNavigate } from '@tanstack/react-router'
import * as React from 'react'

import { useFeatureFlag } from '~/modules/observability'

import { QuestionTable, QuestionTableSkeleton } from '../components/QuestionTable'
import { getPublicQuestions } from '../lib/api'
import { DIFFICULTY_LABELS, kindLabel, QUESTION_KIND_LABELS } from '../lib/labels'
import type { QuestionCardData, QuestionKind, QuestionSearchParams } from '../lib/types'

const YEAR_OPTIONS = [2025, 2024, 2023, 2022]

interface QuestionBrowserContainerProps {
  search: QuestionSearchParams
}

export function QuestionBrowserContainer({ search }: QuestionBrowserContainerProps) {
  const enabled = useFeatureFlag('question_bank', { strict: true })
  const navigate = useNavigate()

  const [loading, setLoading] = React.useState(true)
  const [error, setError] = React.useState<string | null>(null)
  const [questions, setQuestions] = React.useState<QuestionCardData[]>([])
  const [nextCursor, setNextCursor] = React.useState<string | undefined>(undefined)
  const [loadingMore, setLoadingMore] = React.useState(false)
  const [searchText, setSearchText] = React.useState(search.q ?? '')

  // Keep search input synced with url
  React.useEffect(() => {
    setSearchText(search.q ?? '')
  }, [search.q])

  const updateFilters = React.useCallback(
    (patch: Partial<QuestionSearchParams>) => {
      const next = { ...search, ...patch, cursor: undefined }
      // Clean empty values
      Object.keys(next).forEach((k) => {
        const key = k as keyof QuestionSearchParams
        if (next[key] === undefined || next[key] === '' || next[key] === null) {
          delete next[key]
        }
      })
      navigate({
        to: '/app/questions',
        search: next,
      })
    },
    [navigate, search],
  )

  // Debounced search input
  React.useEffect(() => {
    if (searchText === (search.q ?? '')) return
    const timer = setTimeout(() => {
      updateFilters({ q: searchText.trim() || undefined })
    }, 400)
    return () => clearTimeout(timer)
  }, [searchText, search.q, updateFilters])

  // Fetch questions on search params change
  React.useEffect(() => {
    if (!enabled) return
    let active = true
    setLoading(true)
    setError(null)

    getPublicQuestions(search)
      .then((res) => {
        if (!active) return
        setQuestions(res.items)
        setNextCursor(res.next_cursor)
      })
      .catch((err) => {
        if (!active) return
        setError(err instanceof Error ? err.message : 'Could not load questions.')
      })
      .finally(() => {
        if (active) setLoading(false)
      })

    return () => {
      active = false
    }
  }, [search, enabled])

  const handleLoadMore = async () => {
    if (!nextCursor) return
    setLoadingMore(true)
    try {
      const res = await getPublicQuestions({ ...search, cursor: nextCursor })
      setQuestions((prev) => [...prev, ...res.items])
      setNextCursor(res.next_cursor)
    } catch {
      // Keep existing list on failure
    } finally {
      setLoadingMore(false)
    }
  }

  if (!enabled) {
    return (
      <Page width="form">
        <Alert variant="info">The Question Bank feature is currently in rollout and not available yet.</Alert>
      </Page>
    )
  }

  const clearAll = () => navigate({ to: '/app/questions', search: {} })

  const activeFilterList: Array<{ key: string; label: string; onRemove: () => void }> = []
  if (search.q) {
    activeFilterList.push({
      key: 'q',
      label: `Search: "${search.q}"`,
      onRemove: () => updateFilters({ q: undefined }),
    })
  }
  if (search.kind) {
    activeFilterList.push({
      key: 'kind',
      label: `Kind: ${kindLabel(search.kind)}`,
      onRemove: () => updateFilters({ kind: undefined }),
    })
  }
  if (search.difficulty) {
    const level = DIFFICULTY_LABELS[search.difficulty]
    activeFilterList.push({
      key: 'difficulty',
      label: `Difficulty: ${search.difficulty}${level ? ` (${level})` : ''}`,
      onRemove: () => updateFilters({ difficulty: undefined }),
    })
  }
  if (search.year) {
    activeFilterList.push({
      key: 'year',
      label: `Year: ${search.year}`,
      onRemove: () => updateFilters({ year: undefined }),
    })
  }
  if (search.subject) {
    activeFilterList.push({
      key: 'subject',
      label: `Subject: ${search.subject}`,
      onRemove: () => updateFilters({ subject: undefined }),
    })
  }
  if (search.chapter) {
    activeFilterList.push({
      key: 'chapter',
      label: `Chapter: ${search.chapter}`,
      onRemove: () => updateFilters({ chapter: undefined }),
    })
  }

  const years = search.year && !YEAR_OPTIONS.includes(search.year) ? [search.year, ...YEAR_OPTIONS] : YEAR_OPTIONS

  return (
    <Page>
      <PageHeader
        title="Question Bank"
        description="Browse, filter and practise past paper and syllabus questions."
        actions={
          <Button asChild>
            <Link
              to="/app/practice/new"
              search={{
                subject: search.subject,
                chapter: search.chapter,
                kind: search.kind,
              }}
            >
              Practise these questions
            </Link>
          </Button>
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
              type="search"
              aria-label="Search questions"
              placeholder="Search questions or keywords"
              value={searchText}
              onChange={(e) => setSearchText(e.target.value)}
              className="w-full pl-8 sm:w-64"
            />
          </div>

          <Select
            value={search.kind || 'all'}
            onValueChange={(val) => updateFilters({ kind: val === 'all' ? undefined : (val as QuestionKind) })}
          >
            <SelectTrigger aria-label="Kind" className="w-44">
              <SelectValue placeholder="All kinds" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All kinds</SelectItem>
              {Object.entries(QUESTION_KIND_LABELS).map(([value, label]) => (
                <SelectItem key={value} value={value}>
                  {label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>

          <Select
            value={search.difficulty ? String(search.difficulty) : 'all'}
            onValueChange={(val) => updateFilters({ difficulty: val === 'all' ? undefined : Number(val) })}
          >
            <SelectTrigger aria-label="Difficulty" className="w-44">
              <SelectValue placeholder="All difficulties" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All difficulties</SelectItem>
              {Object.entries(DIFFICULTY_LABELS).map(([level, label]) => (
                <SelectItem key={level} value={level}>
                  Level {level} ({label})
                </SelectItem>
              ))}
            </SelectContent>
          </Select>

          <Select
            value={search.year ? String(search.year) : 'all'}
            onValueChange={(val) => updateFilters({ year: val === 'all' ? undefined : Number(val) })}
          >
            <SelectTrigger aria-label="Year" className="w-32">
              <SelectValue placeholder="All years" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All years</SelectItem>
              {years.map((y) => (
                <SelectItem key={y} value={String(y)}>
                  {y}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>

          {!loading && !error && questions.length > 0 && (
            <p aria-live="polite" className="text-xs text-muted-foreground tabular-nums sm:ml-auto">
              Showing {questions.length}
              {nextCursor ? '+' : ''}
            </p>
          )}
        </TableToolbar>

        {activeFilterList.length > 0 && (
          <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
            <span className="text-xs text-muted-foreground">Active filters:</span>
            {activeFilterList.map((chip) => (
              <FilterChip key={chip.key} removeLabel={`Remove ${chip.label}`} onRemove={chip.onRemove}>
                {chip.label}
              </FilterChip>
            ))}
            <Button type="button" variant="ghost" size="xs" onClick={clearAll}>
              Clear all
            </Button>
          </div>
        )}
      </div>

      {loading ? (
        <QuestionTableSkeleton />
      ) : error ? (
        <Alert variant="error">
          {error}
          <div className="mt-2">
            <Button size="sm" variant="outline" onClick={() => updateFilters({})}>
              Retry
            </Button>
          </div>
        </Alert>
      ) : questions.length === 0 ? (
        <EmptyState
          title="No questions match your filters"
          description="Try broadening your search or clearing difficulty and year filters."
          action={
            activeFilterList.length > 0 ? (
              <Button variant="outline" size="sm" onClick={clearAll}>
                Reset all filters
              </Button>
            ) : undefined
          }
        />
      ) : (
        <div className="space-y-3">
          <QuestionTable questions={questions} />

          {nextCursor && (
            <div className="flex justify-center">
              <Button variant="outline" size="sm" loading={loadingMore} onClick={handleLoadMore}>
                Load more questions
              </Button>
            </div>
          )}
        </div>
      )}
    </Page>
  )
}
