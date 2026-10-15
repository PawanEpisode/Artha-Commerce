import {
  Alert,
  Button,
  Card,
  EmptyState,
  FilterChip,
  Input,
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
  Skeleton,
} from '@artha/design-system'
import { Link, useNavigate } from '@tanstack/react-router'
import * as React from 'react'

import { useFeatureFlag } from '~/modules/observability'

import { QuestionCard } from '../components/QuestionCard'
import { getPublicQuestions } from '../lib/api'
import type { QuestionCardData, QuestionKind, QuestionSearchParams } from '../lib/types'

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
    try {
      const res = await getPublicQuestions({ ...search, cursor: nextCursor })
      setQuestions((prev) => [...prev, ...res.items])
      setNextCursor(res.next_cursor)
    } catch {
      // Keep existing list on failure
    }
  }

  if (!enabled) {
    return (
      <div className="mx-auto max-w-4xl px-4 py-12">
        <Alert variant="info">The Question Bank feature is currently in rollout and not available yet.</Alert>
      </div>
    )
  }

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
      label: `Kind: ${search.kind}`,
      onRemove: () => updateFilters({ kind: undefined }),
    })
  }
  if (search.difficulty) {
    activeFilterList.push({
      key: 'difficulty',
      label: `Diff: ${search.difficulty}`,
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

  return (
    <div className="mx-auto max-w-5xl space-y-6 px-4 py-8">
      {/* Header and Search */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="font-display text-2xl font-bold tracking-tight text-foreground sm:text-3xl">Question Bank</h1>
          <p className="text-sm text-muted-foreground">
            Browse, filter and practise past paper and syllabus questions.
          </p>
        </div>

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
      </div>

      {/* Filter Toolbar */}
      <Card className="space-y-4 p-4">
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <Input
            placeholder="Search questions or keywords..."
            value={searchText}
            onChange={(e) => setSearchText(e.target.value)}
            className="w-full"
          />

          <Select
            value={search.kind || 'all'}
            onValueChange={(val) => updateFilters({ kind: val === 'all' ? undefined : (val as QuestionKind) })}
          >
            <SelectTrigger>
              <SelectValue placeholder="All kinds" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All kinds</SelectItem>
              <SelectItem value="mcq_single">MCQ Single Choice</SelectItem>
              <SelectItem value="mcq_multi">MCQ Multiple Choice</SelectItem>
              <SelectItem value="numeric">Numeric</SelectItem>
              <SelectItem value="case_study">Case Study</SelectItem>
              <SelectItem value="true_false">True / False</SelectItem>
              <SelectItem value="long_form">Long Form</SelectItem>
            </SelectContent>
          </Select>

          <Select
            value={search.difficulty ? String(search.difficulty) : 'all'}
            onValueChange={(val) => updateFilters({ difficulty: val === 'all' ? undefined : Number(val) })}
          >
            <SelectTrigger>
              <SelectValue placeholder="All difficulties" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All difficulties</SelectItem>
              <SelectItem value="1">Level 1 (Foundational)</SelectItem>
              <SelectItem value="2">Level 2 (Easy)</SelectItem>
              <SelectItem value="3">Level 3 (Moderate)</SelectItem>
              <SelectItem value="4">Level 4 (Hard)</SelectItem>
              <SelectItem value="5">Level 5 (Exam level)</SelectItem>
            </SelectContent>
          </Select>

          <Select
            value={search.year ? String(search.year) : 'all'}
            onValueChange={(val) => updateFilters({ year: val === 'all' ? undefined : Number(val) })}
          >
            <SelectTrigger>
              <SelectValue placeholder="All years" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All years</SelectItem>
              <SelectItem value="2025">2025</SelectItem>
              <SelectItem value="2024">2024</SelectItem>
              <SelectItem value="2023">2023</SelectItem>
              <SelectItem value="2022">2022</SelectItem>
            </SelectContent>
          </Select>
        </div>

        {/* Active filter chips */}
        {activeFilterList.length > 0 && (
          <div className="flex flex-wrap items-center gap-2 border-t border-border/60 pt-3">
            <span className="text-xs text-muted-foreground">Active filters:</span>
            {activeFilterList.map((chip) => (
              <FilterChip key={chip.key} removeLabel={`Remove ${chip.label}`} onRemove={chip.onRemove}>
                {chip.label}
              </FilterChip>
            ))}
            <button
              type="button"
              onClick={() => navigate({ to: '/app/questions', search: {} })}
              className="text-xs font-medium text-primary hover:underline"
            >
              Clear all
            </button>
          </div>
        )}
      </Card>

      {/* Questions List */}
      {loading ? (
        <div className="space-y-3">
          {[1, 2, 3, 4, 5].map((i) => (
            <Skeleton key={i} className="h-28 w-full rounded-xl" />
          ))}
        </div>
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
              <Button variant="outline" onClick={() => navigate({ to: '/app/questions', search: {} })}>
                Reset all filters
              </Button>
            ) : undefined
          }
        />
      ) : (
        <div className="space-y-3">
          <div className="flex items-center justify-between text-xs text-muted-foreground">
            <span>Showing {questions.length} questions</span>
          </div>

          <div className="space-y-3">
            {questions.map((q) => (
              <QuestionCard key={q.id} question={q} />
            ))}
          </div>

          {nextCursor && (
            <div className="pt-4 text-center">
              <Button variant="outline" onClick={handleLoadMore}>
                Load more questions
              </Button>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
