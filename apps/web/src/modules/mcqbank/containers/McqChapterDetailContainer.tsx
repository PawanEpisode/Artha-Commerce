import {
  Badge,
  Button,
  Card,
  CardContent,
  EmptyState,
  Page,
  PageHeader,
  Play,
  ProgressBar,
  Skeleton,
  toastApiError,
} from '@artha/design-system'
import { Link, useNavigate } from '@tanstack/react-router'
import { useEffect, useState } from 'react'

import { ChapterPracticeBar } from '../components/ChapterPracticeBar'
import { ExternalLogDialog } from '../components/ExternalLogDialog'
import { SetsTable } from '../components/SetsTable'
import { getChapterDetail, startQuickPractice, startSetPractice } from '../lib/api'
import type { ChapterDetailData, McqSetCard, PracticeFeedback } from '../lib/types'
import { ChapterQuestionsContainer } from './ChapterQuestionsContainer'

interface McqChapterDetailContainerProps {
  subjectKey: string
  chapterKey: string
}

export function McqChapterDetailContainer({ subjectKey, chapterKey }: McqChapterDetailContainerProps) {
  const navigate = useNavigate()
  const [data, setData] = useState<ChapterDetailData | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [isStarting, setIsStarting] = useState(false)
  const [logDialogSet, setLogDialogSet] = useState<McqSetCard | null>(null)

  useEffect(() => {
    async function load() {
      try {
        const detail = await getChapterDetail(subjectKey, chapterKey)
        // The API answers `{}` for a chapter it does not know.
        setData(detail?.chapter_id ? detail : null)
      } catch (err: unknown) {
        toastApiError(err, 'Failed to load chapter details')
      } finally {
        setIsLoading(false)
      }
    }
    load()
  }, [subjectKey, chapterKey])

  async function handleStartPractice(count: number, feedback: PracticeFeedback) {
    if (!data || isStarting) return
    try {
      setIsStarting(true)
      const res = await startQuickPractice({
        chapter_id: data.chapter_id,
        subject_key: subjectKey,
        count,
        mode: 'chapter_quiz',
        feedback_policy: feedback,
      })
      navigate({
        to: '/app/practice/session/$id',
        params: { id: res.session_id },
      })
    } catch (err: unknown) {
      toastApiError(err, 'Could not start quiz')
      setIsStarting(false)
    }
  }

  async function handleStartSet(slug: string) {
    try {
      setIsStarting(true)
      const res = await startSetPractice(slug, 'untimed')
      navigate({
        to: '/app/practice/session/$id',
        params: { id: res.session_id },
      })
    } catch (err: unknown) {
      toastApiError(err, 'Could not start set')
      setIsStarting(false)
    }
  }

  if (isLoading) {
    return (
      <Page>
        <div role="status" aria-busy="true" aria-label="Loading chapter" className="space-y-3">
          <Skeleton className="h-8 w-64" />
          <Skeleton className="h-32 w-full" />
        </div>
      </Page>
    )
  }

  if (!data) {
    return (
      <Page>
        <EmptyState title="Chapter not found." />
      </Page>
    )
  }

  const totalDiff = data.difficulty_split.easy + data.difficulty_split.medium + data.difficulty_split.hard
  const bands = [
    { key: 'easy', label: 'Easy (L1-L2)', value: data.difficulty_split.easy, tone: 'text-success-fg' },
    { key: 'medium', label: 'Medium (L3)', value: data.difficulty_split.medium, tone: 'text-warning-fg' },
    { key: 'hard', label: 'Hard (L4-L5)', value: data.difficulty_split.hard, tone: 'text-destructive' },
  ]

  return (
    <Page>
      <PageHeader
        eyebrow={
          <Link to="/app/mcq/subjects/$subject" params={{ subject: subjectKey }} className="hover:underline">
            Subject chapters
          </Link>
        }
        title={
          <span className="inline-flex items-center gap-2">
            {data.name}
            {data.section && <Badge variant="outline">{data.section}</Badge>}
          </span>
        }
        description="Chapter breakdown, difficulty distribution, and targeted practice sets."
        actions={
          <Button disabled={isStarting || data.available === 0} onClick={() => handleStartPractice(10, 'instant')}>
            <Play aria-hidden className="size-3.5 fill-current" />
            Start 10 MCQs
          </Button>
        }
      />

      <div className="grid gap-3 md:grid-cols-3">
        <Card className="md:col-span-1">
          <CardContent className="space-y-3">
            <h2 className="text-sm font-semibold text-foreground">Difficulty distribution</h2>
            {bands.map((b) => (
              <div key={b.key}>
                <div className="mb-1 flex justify-between text-xs">
                  <span className={`font-medium ${b.tone}`}>{b.label}</span>
                  <span className="text-muted-foreground tabular-nums">{b.value} MCQs</span>
                </div>
                <ProgressBar
                  value={totalDiff > 0 ? (b.value / totalDiff) * 100 : 0}
                  label={`${b.key[0]?.toUpperCase()}${b.key.slice(1)} MCQs share`}
                  className="h-1.5"
                />
              </div>
            ))}
          </CardContent>
        </Card>

        <Card className="md:col-span-2">
          <CardContent className="space-y-2">
            <h2 className="text-sm font-semibold text-foreground">Syllabus topics ({data.topics.length})</h2>

            {data.topics.length > 0 ? (
              <div className="divide-y text-[13px]">
                {data.topics.map((t) => (
                  <div key={t.id} className="flex items-center justify-between py-1.5">
                    <span className="font-medium text-foreground">{t.name}</span>
                    <span className="text-muted-foreground tabular-nums">{t.count} MCQs</span>
                  </div>
                ))}
              </div>
            ) : (
              <div className="text-xs text-muted-foreground">No sub-topics listed for this chapter.</div>
            )}
          </CardContent>
        </Card>
      </div>

      <ChapterPracticeBar available={data.available} isStarting={isStarting} onStart={handleStartPractice} />

      <ChapterQuestionsContainer key={data.chapter_id} chapterId={data.chapter_id} />

      {data.sets.length > 0 && (
        <section className="space-y-2">
          <h2 className="text-sm font-semibold text-foreground">Targeted practice sets</h2>
          <SetsTable
            sets={data.sets}
            onStartPractice={handleStartSet}
            onOpenExternalLog={(item) => setLogDialogSet(item)}
            isStarting={isStarting}
          />
        </section>
      )}

      <ExternalLogDialog
        open={!!logDialogSet}
        onOpenChange={(open) => !open && setLogDialogSet(null)}
        set={logDialogSet}
      />
    </Page>
  )
}
