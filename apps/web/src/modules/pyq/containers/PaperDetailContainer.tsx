import {
  Alert,
  ArrowLeft,
  ArrowUpRight,
  Badge,
  Button,
  ButtonLink,
  Card,
  Clock,
  Play,
  Skeleton,
  toast,
} from '@artha/design-system'
import { Link, useNavigate } from '@tanstack/react-router'
import * as React from 'react'

import { useFeatureFlag } from '~/modules/observability'

import { PaperQuestionTree } from '../components/PaperQuestionTree'
import { getPaperDetail, startPaperPractice } from '../lib/api'
import type { PyqPaperDetail } from '../lib/types'

interface PaperDetailContainerProps {
  paperId: string
}

export function PaperDetailContainer({ paperId }: PaperDetailContainerProps) {
  const enabled = useFeatureFlag('pyq_bank', { strict: true })
  const navigate = useNavigate()

  const [loading, setLoading] = React.useState(true)
  const [paper, setPaper] = React.useState<PyqPaperDetail | null>(null)
  const [isStarting, setIsStarting] = React.useState(false)
  const [error, setError] = React.useState<string | null>(null)

  React.useEffect(() => {
    if (!enabled) return
    let active = true
    setLoading(true)
    setError(null)

    getPaperDetail(paperId)
      .then((data) => {
        if (!active) return
        if (!data) {
          setError('Paper not found.')
        } else {
          setPaper(data)
        }
      })
      .catch(() => {
        if (active) setError('Failed to load paper details.')
      })
      .finally(() => {
        if (active) setLoading(false)
      })

    return () => {
      active = false
    }
  }, [enabled, paperId])

  const handleStartPractice = async (mode: 'untimed' | 'timed') => {
    if (!paper) return
    setIsStarting(true)
    try {
      const res = await startPaperPractice(paper.id, { mode })
      toast.success(mode === 'timed' ? 'Exam simulation started!' : 'Practice session started!')
      navigate({
        to: '/app/practice/session/$id',
        params: { id: res.session_id },
      })
    } catch {
      toast.error('Could not start practice session.')
    } finally {
      setIsStarting(false)
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

  if (loading) {
    return (
      <div className="mx-auto max-w-5xl space-y-6 px-4 py-8">
        <Skeleton className="h-6 w-32" />
        <Skeleton className="h-10 w-3/4" />
        <Skeleton className="h-32 w-full" />
      </div>
    )
  }

  if (error || !paper) {
    return (
      <div className="mx-auto max-w-5xl space-y-6 px-4 py-8">
        <ButtonLink asChild variant="outline" size="sm" className="gap-1.5">
          <Link to="/app/pyq">
            <ArrowLeft className="size-4" />
            Back to Past Papers
          </Link>
        </ButtonLink>
        <Alert variant="error">{error || 'Paper not found.'}</Alert>
      </div>
    )
  }

  const isCurrentScheme = paper.syllabus_status === 'current'

  return (
    <div className="mx-auto max-w-5xl space-y-8 px-4 py-8">
      {/* Back button */}
      <div>
        <ButtonLink asChild variant="ghost" size="sm" className="gap-1.5 text-muted-foreground hover:text-foreground">
          <Link to="/app/pyq">
            <ArrowLeft className="size-4" />
            All Past Papers
          </Link>
        </ButtonLink>
      </div>

      {/* Header Banner */}
      <div className="space-y-4">
        <div className="flex flex-wrap items-center gap-2">
          <Badge variant="outline" className="font-semibold text-primary">
            {paper.term_code.replace('_', ' ').toUpperCase()}
          </Badge>
          <Badge variant="default" className="font-mono text-xs uppercase">
            {paper.paper_code || paper.subject_key}
          </Badge>
          {isCurrentScheme ? (
            <span className="inline-flex items-center rounded-full bg-emerald-50 px-2 py-0.5 text-xs font-medium text-emerald-700 dark:bg-emerald-950/40 dark:text-emerald-300">
              2022 Syllabus
            </span>
          ) : (
            <span className="inline-flex items-center rounded-full bg-amber-50 px-2 py-0.5 text-xs font-medium text-amber-700 dark:bg-amber-950/40 dark:text-amber-300">
              Mapped Syllabus
            </span>
          )}
        </div>

        <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
          <div>
            <h1 className="text-2xl font-bold tracking-tight text-foreground sm:text-3xl">{paper.title}</h1>
            <p className="mt-1 text-sm text-muted-foreground capitalize">
              {paper.course_code.toUpperCase()} • {paper.level_code.replace('_', ' ').toUpperCase()}
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-2.5">
            <Button
              variant="outline"
              onClick={() => handleStartPractice('untimed')}
              disabled={isStarting}
              className="gap-1.5"
            >
              <Play className="size-3.5 fill-current" />
              Practise Mode
            </Button>
            <Button onClick={() => handleStartPractice('timed')} disabled={isStarting} className="gap-1.5">
              <Clock className="size-3.5" />
              Simulate Exam
            </Button>
          </div>
        </div>

        {/* Paper Stats strip */}
        <div className="grid grid-cols-2 gap-3 pt-2 sm:grid-cols-4">
          <Card className="p-3">
            <span className="block text-xs text-muted-foreground">Total Marks</span>
            <span className="text-lg font-bold text-foreground">{paper.total_marks}</span>
          </Card>
          <Card className="p-3">
            <span className="block text-xs text-muted-foreground">Duration</span>
            <span className="text-lg font-bold text-foreground">{paper.duration_minutes ?? 180} mins</span>
          </Card>
          <Card className="p-3">
            <span className="block text-xs text-muted-foreground">Reading Time</span>
            <span className="text-lg font-bold text-foreground">{paper.reading_minutes ?? 15} mins</span>
          </Card>
          <Card className="p-3">
            <span className="block text-xs text-muted-foreground">Questions</span>
            <span className="text-lg font-bold text-foreground">{paper.question_count} items</span>
          </Card>
        </div>
      </div>

      {/* Official Links & Notes */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        {paper.links.length > 0 && (
          <Card className="space-y-3 p-4">
            <h3 className="text-xs font-bold tracking-wider text-muted-foreground uppercase">
              Official ICMAI Documents
            </h3>
            <ul className="space-y-2 text-sm">
              {paper.links.map((link) => (
                <li key={link.id}>
                  <a
                    href={link.url}
                    target="_blank"
                    rel="noreferrer noopener"
                    className="inline-flex items-center gap-1.5 font-medium text-primary hover:underline"
                  >
                    <ArrowUpRight className="size-4 shrink-0" />
                    <span>{link.label || 'Official Document'}</span>
                    <span className="font-mono text-xs text-muted-foreground">({link.host})</span>
                  </a>
                </li>
              ))}
            </ul>
          </Card>
        )}

        {(paper.marks_note || paper.law_note) && (
          <Card className="space-y-2 p-4 text-xs text-muted-foreground">
            <h3 className="font-bold tracking-wider text-foreground uppercase">Exam Instructions & Notes</h3>
            {paper.marks_note && <p>{paper.marks_note}</p>}
            {paper.law_note && <p className="italic">{paper.law_note}</p>}
          </Card>
        )}
      </div>

      {/* Choice Structure summary */}
      {paper.choice_groups.length > 0 && (
        <Card className="space-y-2 bg-muted/30 p-4">
          <h3 className="text-xs font-bold tracking-wider text-foreground uppercase">Choice & Paper Structure</h3>
          <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
            {paper.choice_groups.map((cg) => (
              <div key={cg.id} className="text-xs text-muted-foreground">
                <span className="font-semibold text-foreground">{cg.section_label}: </span>
                {cg.label}
              </div>
            ))}
          </div>
        </Card>
      )}

      {/* Questions Breakdown */}
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-bold text-foreground">Questions Breakdown</h2>
          <span className="text-xs text-muted-foreground">
            Click &quot;Practise&quot; on any question to solve it individually
          </span>
        </div>

        <PaperQuestionTree questions={paper.questions} choiceGroups={paper.choice_groups} />
      </div>
    </div>
  )
}
