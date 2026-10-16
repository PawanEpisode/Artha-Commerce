import {
  Alert,
  ArrowLeft,
  ArrowUpRight,
  Badge,
  Button,
  ButtonLink,
  Card,
  CardContent,
  Clock,
  Page,
  PageHeader,
  Play,
  Skeleton,
  StatTile,
  toast,
} from '@artha/design-system'
import { Link, useNavigate } from '@tanstack/react-router'
import * as React from 'react'

import { useFeatureFlag } from '~/modules/observability'

import { PaperQuestionTree } from '../components/PaperQuestionTree'
import { getPaperDetail, startPaperPractice } from '../lib/api'
import { levelLabel, marksText, termLabel } from '../lib/labels'
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
      <Page width="form">
        <Alert variant="info">
          The Previous Year Questions (PYQ) bank is currently under rollout and not yet available.
        </Alert>
      </Page>
    )
  }

  if (loading) {
    return (
      <Page>
        <div role="status" aria-busy="true" aria-label="Loading paper" className="space-y-3">
          <Skeleton className="h-6 w-32" />
          <Skeleton className="h-8 w-3/4" />
          <Skeleton className="h-20 w-full" />
        </div>
      </Page>
    )
  }

  if (error || !paper) {
    return (
      <Page>
        <ButtonLink asChild variant="outline" size="sm" className="gap-1.5">
          <Link to="/app/pyq">
            <ArrowLeft aria-hidden className="size-4" />
            Back to Past Papers
          </Link>
        </ButtonLink>
        <Alert variant="error">{error || 'Paper not found.'}</Alert>
      </Page>
    )
  }

  const isCurrentScheme = paper.syllabus_status === 'current'

  return (
    <Page>
      <PageHeader
        eyebrow={
          <Link to="/app/pyq" className="hover:underline">
            All Past Papers
          </Link>
        }
        title={paper.title}
        description={
          <span className="flex flex-wrap items-center gap-1.5">
            <span>
              {paper.course_code.toUpperCase()} {levelLabel(paper.level_code)}
            </span>
            <Badge variant="outline">{termLabel(paper.term_code)}</Badge>
            <Badge className="uppercase">{paper.paper_code || paper.subject_key}</Badge>
            {isCurrentScheme ? (
              <Badge variant="outline" className="border-success-border bg-success-bg text-success-fg">
                2022 Syllabus
              </Badge>
            ) : (
              <Badge variant="outline" className="border-warning-border bg-warning-bg text-warning-fg">
                Mapped Syllabus
              </Badge>
            )}
          </span>
        }
        actions={
          <>
            <Button variant="outline" onClick={() => handleStartPractice('untimed')} disabled={isStarting}>
              <Play aria-hidden className="size-3.5 fill-current" />
              Practise Mode
            </Button>
            <Button onClick={() => handleStartPractice('timed')} disabled={isStarting}>
              <Clock aria-hidden className="size-3.5" />
              Simulate Exam
            </Button>
          </>
        }
      />

      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        <StatTile label="Total Marks" value={marksText(paper.total_marks)} />
        <StatTile label="Duration" value={`${paper.duration_minutes ?? 180} mins`} />
        <StatTile label="Reading Time" value={`${paper.reading_minutes ?? 15} mins`} />
        <StatTile label="Questions" value={`${paper.question_count} items`} />
      </div>

      {(paper.links.length > 0 || paper.marks_note || paper.law_note || paper.choice_groups.length > 0) && (
        <div className="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-3">
          {paper.links.length > 0 && (
            <Card>
              <CardContent className="space-y-2">
                <h2 className="text-sm font-semibold text-foreground">Official ICMAI documents</h2>
                <ul className="space-y-1.5 text-[13px]">
                  {paper.links.map((link) => (
                    <li key={link.id}>
                      <a
                        href={link.url}
                        target="_blank"
                        rel="noreferrer noopener"
                        className="inline-flex items-center gap-1.5 font-medium text-primary hover:underline"
                      >
                        <ArrowUpRight aria-hidden className="size-3.5 shrink-0" />
                        <span>{link.label || 'Official Document'}</span>
                        <span className="font-mono text-xs text-muted-foreground">({link.host})</span>
                      </a>
                    </li>
                  ))}
                </ul>
              </CardContent>
            </Card>
          )}

          {(paper.marks_note || paper.law_note) && (
            <Card>
              <CardContent className="space-y-1.5 text-xs text-muted-foreground">
                <h2 className="text-sm font-semibold text-foreground">Exam instructions and notes</h2>
                {paper.marks_note && <p>{paper.marks_note}</p>}
                {paper.law_note && <p className="italic">{paper.law_note}</p>}
              </CardContent>
            </Card>
          )}

          {paper.choice_groups.length > 0 && (
            <Card className="bg-muted/30">
              <CardContent className="space-y-1.5">
                <h2 className="text-sm font-semibold text-foreground">Choice and paper structure</h2>
                <ul className="space-y-1">
                  {paper.choice_groups.map((cg) => (
                    <li key={cg.id} className="text-xs text-muted-foreground">
                      <span className="font-medium text-foreground">{cg.section_label}: </span>
                      {cg.label}
                    </li>
                  ))}
                </ul>
              </CardContent>
            </Card>
          )}
        </div>
      )}

      <section className="space-y-2">
        <div className="flex flex-wrap items-baseline justify-between gap-x-3">
          <h2 className="text-sm font-semibold text-foreground">Questions breakdown</h2>
          <span className="text-xs text-muted-foreground">
            Click &quot;Practise&quot; on any question to solve it individually
          </span>
        </div>

        <PaperQuestionTree questions={paper.questions} choiceGroups={paper.choice_groups} />
      </section>
    </Page>
  )
}
