import {
  Alert,
  Badge,
  Button,
  ButtonLink,
  Card,
  CardContent,
  Flag,
  Page,
  PageHeader,
  ShieldCheck,
  Skeleton,
} from '@artha/design-system'
import { Link } from '@tanstack/react-router'
import * as React from 'react'

import { RichText } from '~/lib/richtext'
import { useFeatureFlag } from '~/modules/observability'
import { QuestionCardButton } from '~/modules/recall'

import { QuestionOptionsList } from '../components/QuestionOptionsList'
import { DifficultyDots } from '../components/QuestionTable'
import { ReportErrorDialog } from '../components/ReportErrorDialog'
import { getPlayableQuestion, getReviewQuestion } from '../lib/api'
import { DIFFICULTY_LABELS, formatMarks, kindLabel, numericKeyText, QUESTION_TEXT_CLASS } from '../lib/labels'
import type { ReviewQuestion } from '../lib/types'

interface QuestionDetailContainerProps {
  questionId: string
}

const labelText = (labels: Record<string, unknown> | undefined, key: string): string => {
  const v = labels?.[key]
  return typeof v === 'string' || typeof v === 'number' ? String(v) : ''
}

function MetaRow({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex items-center justify-between gap-3 px-4 py-2 text-[13px]">
      <dt className="shrink-0 text-muted-foreground">{label}</dt>
      <dd className="min-w-0 text-right font-medium text-foreground">{children}</dd>
    </div>
  )
}

export function QuestionDetailContainer({ questionId }: QuestionDetailContainerProps) {
  const enabled = useFeatureFlag('question_bank', { strict: true })

  const [loading, setLoading] = React.useState(true)
  const [error, setError] = React.useState<string | null>(null)
  const [data, setData] = React.useState<ReviewQuestion | null>(null)

  React.useEffect(() => {
    if (!enabled) return
    let active = true
    setLoading(true)
    setError(null)

    // Try review endpoint first, then playable
    getReviewQuestion(questionId)
      .then((res) => {
        if (!active) return
        setData(res)
      })
      .catch(async () => {
        try {
          const playable = await getPlayableQuestion(questionId)
          if (!active) return
          setData({
            ...playable,
            correct_option_ids: [],
            negative_marks: 0,
          })
        } catch (err) {
          if (!active) return
          setError(err instanceof Error ? err.message : 'Could not load question details.')
        }
      })
      .finally(() => {
        if (active) setLoading(false)
      })

    return () => {
      active = false
    }
  }, [questionId, enabled])

  if (!enabled) {
    return (
      <Page width="form">
        <Alert variant="info">The Question Bank feature is currently in rollout and not available yet.</Alert>
      </Page>
    )
  }

  if (loading) {
    return (
      <Page>
        <Skeleton className="h-6 w-40" />
        <div
          role="status"
          aria-busy="true"
          aria-label="Loading question"
          className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_22rem]"
        >
          <div className="space-y-3">
            <Skeleton className="h-32 w-full rounded-lg" />
            <Skeleton className="h-10 w-full rounded-lg" />
            <Skeleton className="h-10 w-full rounded-lg" />
            <Skeleton className="h-10 w-full rounded-lg" />
          </div>
          <Skeleton className="h-64 w-full rounded-lg" />
        </div>
      </Page>
    )
  }

  if (error || !data) {
    return (
      <Page>
        <Alert variant="error">
          {error ?? 'Question not found.'}
          <div className="mt-3">
            <ButtonLink asChild variant="outline" size="sm">
              <Link to="/app/questions">Back to questions</Link>
            </ButtonLink>
          </div>
        </Alert>
      </Page>
    )
  }

  const labels = data.labels
  const difficulty = Number(labelText(labels, 'difficulty')) || undefined
  const source = [labelText(labels, 'source_name'), labelText(labels, 'source_year')].filter(Boolean).join(' ')
  const sourceRef = labelText(labels, 'source_ref')
  const nature = labelText(labels, 'nature')
  const verified = labels?.verified === true
  const negative = Number(data.negative_marks) > 0
  const numericKey = data.kind === 'numeric' ? numericKeyText(data.numeric_key) : null

  return (
    <Page>
      <PageHeader
        title="Question"
        description={`${kindLabel(data.kind)} · ${formatMarks(data.marks)}`}
        actions={
          <ButtonLink asChild variant="ghost" size="sm">
            <Link to="/app/questions">Back to questions</Link>
          </ButtonLink>
        }
      />

      <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_22rem] lg:items-start">
        <div className="min-w-0 space-y-4">
          <Card>
            <CardContent className="space-y-4 pt-4">
              <RichText markdown={data.stem_md} profile="question" className={QUESTION_TEXT_CLASS} />

              {data.options && data.options.length > 0 && (
                <div className="space-y-2">
                  <h2 className="text-[11px] font-medium tracking-wide text-muted-foreground uppercase">Options</h2>
                  <QuestionOptionsList options={data.options} correctOptionIds={data.correct_option_ids} revealed />
                </div>
              )}

              {numericKey !== null && (
                <div className="rounded-md border border-border bg-muted/40 px-3 py-2">
                  <p className="text-xs text-muted-foreground">Correct numerical value</p>
                  <p className="text-base font-semibold text-foreground tabular-nums">{numericKey}</p>
                </div>
              )}
            </CardContent>
          </Card>

          {data.explanation_md && (
            <Card>
              <CardContent className="space-y-2 pt-4">
                <h2 className="text-sm font-semibold text-foreground">Explanation and solution</h2>
                <RichText markdown={data.explanation_md} profile="question" className={QUESTION_TEXT_CLASS} />

                {data.reference_labels && data.reference_labels.length > 0 && (
                  <div className="flex flex-wrap items-center gap-1.5 pt-1">
                    <span className="text-xs text-muted-foreground">References:</span>
                    {data.reference_labels.map((ref, i) => (
                      <Badge key={i} variant="outline">
                        {ref}
                      </Badge>
                    ))}
                  </div>
                )}
              </CardContent>
            </Card>
          )}
        </div>

        <aside
          aria-label="Question details"
          className="space-y-3 lg:sticky lg:top-[calc(var(--site-header-height)+1rem)]"
        >
          <Card>
            <dl className="divide-y">
              <MetaRow label="Kind">
                <Badge variant="outline">{kindLabel(data.kind)}</Badge>
              </MetaRow>
              <MetaRow label="Marks">
                <span className="tabular-nums">{Number(data.marks)}</span>
                {negative && <span className="ml-1.5 text-destructive">(-{Number(data.negative_marks)} wrong)</span>}
              </MetaRow>
              {difficulty && (
                <MetaRow label="Difficulty">
                  <span className="inline-flex items-center gap-2">
                    <DifficultyDots level={difficulty} />
                    <span className="tabular-nums">
                      {difficulty}/5{DIFFICULTY_LABELS[difficulty] ? ` ${DIFFICULTY_LABELS[difficulty]}` : ''}
                    </span>
                  </span>
                </MetaRow>
              )}
              {source && <MetaRow label="Source">{source}</MetaRow>}
              {sourceRef && <MetaRow label="Reference">{sourceRef}</MetaRow>}
              {nature && (
                <MetaRow label="Nature">
                  <span className="capitalize">{nature.replace(/_/g, ' ')}</span>
                </MetaRow>
              )}
              <MetaRow label="Status">
                <span className="inline-flex flex-wrap items-center justify-end gap-x-2 gap-y-0.5">
                  {verified && (
                    <span className="inline-flex items-center gap-1 text-success-fg">
                      <ShieldCheck aria-hidden className="size-3.5" /> Verified
                    </span>
                  )}
                  <span className="text-muted-foreground">Version {data.version_no}</span>
                  {data.newer_version_available && <Badge variant="highlight">Newer version</Badge>}
                </span>
              </MetaRow>
            </dl>
          </Card>

          <Card>
            <CardContent className="space-y-2 pt-4">
              <h2 className="text-[11px] font-medium tracking-wide text-muted-foreground uppercase">Actions</h2>
              <QuestionCardButton questionId={data.question_id} versionId={data.version_id} />
              <ReportErrorDialog
                questionId={questionId}
                trigger={
                  <Button variant="outline" size="sm" className="w-full justify-start">
                    <Flag aria-hidden /> Report an error
                  </Button>
                }
              />
            </CardContent>
          </Card>
        </aside>
      </div>
    </Page>
  )
}
