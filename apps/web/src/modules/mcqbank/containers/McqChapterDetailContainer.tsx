import {
  ArrowLeft,
  Badge,
  Button,
  ButtonLink,
  Card,
  Container,
  Play,
  ProgressBar,
  Skeleton,
  toast,
} from '@artha/design-system'
import { Link, useNavigate } from '@tanstack/react-router'
import { useEffect, useState } from 'react'

import { ExternalLogDialog } from '../components/ExternalLogDialog'
import { SetCard } from '../components/SetCard'
import { getChapterDetail, startQuickPractice, startSetPractice } from '../lib/api'
import type { ChapterDetailData, McqSetCard } from '../lib/types'

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
        setData(detail)
      } catch (err: unknown) {
        toast.error(err instanceof Error ? err.message : 'Failed to load chapter details')
      } finally {
        setIsLoading(false)
      }
    }
    load()
  }, [subjectKey, chapterKey])

  async function handleQuickPractice() {
    if (!data) return
    try {
      setIsStarting(true)
      const res = await startQuickPractice({
        chapter_id: data.chapter_id,
        subject_key: subjectKey,
        count: 10,
        mode: 'chapter_quiz',
      })
      navigate({
        to: '/app/practice/session/$id',
        params: { id: res.session_id },
      })
    } catch (err: unknown) {
      toast.error(err instanceof Error ? err.message : 'Could not start quiz')
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
      toast.error(err instanceof Error ? err.message : 'Could not start set')
      setIsStarting(false)
    }
  }

  if (isLoading) {
    return (
      <Container className="space-y-6 py-8">
        <Skeleton className="h-6 w-32" />
        <Skeleton className="h-10 w-64" />
        <Skeleton className="h-32 w-full" />
      </Container>
    )
  }

  if (!data) {
    return (
      <Container className="py-8">
        <div className="rounded-lg border border-dashed p-8 text-center text-muted-foreground">Chapter not found.</div>
      </Container>
    )
  }

  const totalDiff = data.difficulty_split.easy + data.difficulty_split.medium + data.difficulty_split.hard

  return (
    <Container className="space-y-8 py-8">
      {/* Navigation */}
      <div className="space-y-4">
        <ButtonLink
          asChild
          variant="ghost"
          size="sm"
          className="-ml-2 gap-1.5 text-xs text-muted-foreground hover:text-foreground"
        >
          <Link to="/app/mcq/subjects/$subject" params={{ subject: subjectKey }}>
            <ArrowLeft className="h-3.5 w-3.5" />
            Back to Subject Chapters
          </Link>
        </ButtonLink>

        <div className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-2xl font-bold tracking-tight text-foreground sm:text-3xl">{data.name}</h1>
              {data.section && <Badge variant="outline">{data.section}</Badge>}
            </div>
            <p className="mt-1 text-sm text-muted-foreground">
              Chapter breakdown, difficulty distribution, and targeted practice sets.
            </p>
          </div>

          <Button
            size="default"
            className="gap-2 font-semibold shadow"
            disabled={isStarting || totalDiff === 0}
            onClick={handleQuickPractice}
          >
            <Play className="h-4 w-4 fill-current" />
            Start 10 MCQs
          </Button>
        </div>
      </div>

      {/* Difficulty Split & Topics */}
      <div className="grid gap-6 md:grid-cols-3">
        {/* Difficulty Breakdown */}
        <Card className="space-y-4 p-5 md:col-span-1">
          <h2 className="text-sm font-semibold tracking-wider text-muted-foreground uppercase">
            Difficulty Distribution
          </h2>

          <div className="space-y-3">
            <div>
              <div className="mb-1 flex justify-between text-xs">
                <span className="font-medium text-emerald-600 dark:text-emerald-400">Easy (L1-L2)</span>
                <span className="text-muted-foreground">{data.difficulty_split.easy} MCQs</span>
              </div>
              <ProgressBar
                value={totalDiff > 0 ? (data.difficulty_split.easy / totalDiff) * 100 : 0}
                label="Easy MCQs share"
                className="h-1.5"
              />
            </div>

            <div>
              <div className="mb-1 flex justify-between text-xs">
                <span className="font-medium text-amber-600 dark:text-amber-400">Medium (L3)</span>
                <span className="text-muted-foreground">{data.difficulty_split.medium} MCQs</span>
              </div>
              <ProgressBar
                value={totalDiff > 0 ? (data.difficulty_split.medium / totalDiff) * 100 : 0}
                label="Medium MCQs share"
                className="h-1.5"
              />
            </div>

            <div>
              <div className="mb-1 flex justify-between text-xs">
                <span className="font-medium text-rose-600 dark:text-rose-400">Hard (L4-L5)</span>
                <span className="text-muted-foreground">{data.difficulty_split.hard} MCQs</span>
              </div>
              <ProgressBar
                value={totalDiff > 0 ? (data.difficulty_split.hard / totalDiff) * 100 : 0}
                label="Hard MCQs share"
                className="h-1.5"
              />
            </div>
          </div>
        </Card>

        {/* Topics List */}
        <Card className="space-y-4 p-5 md:col-span-2">
          <h2 className="text-sm font-semibold tracking-wider text-muted-foreground uppercase">
            Syllabus Topics ({data.topics.length})
          </h2>

          {data.topics.length > 0 ? (
            <div className="divide-y text-xs">
              {data.topics.map((t) => (
                <div key={t.id} className="flex items-center justify-between py-2.5">
                  <span className="font-medium text-foreground">{t.name}</span>
                  <span className="text-muted-foreground">{t.count} MCQs</span>
                </div>
              ))}
            </div>
          ) : (
            <div className="text-xs text-muted-foreground">No sub-topics listed for this chapter.</div>
          )}
        </Card>
      </div>

      {/* Chapter Sets */}
      {data.sets.length > 0 && (
        <div className="space-y-4 border-t pt-4">
          <h2 className="text-lg font-semibold text-foreground">Targeted Practice Sets</h2>

          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {data.sets.map((s) => (
              <SetCard
                key={s.id}
                set={s}
                onStartPractice={handleStartSet}
                onOpenExternalLog={(item) => setLogDialogSet(item)}
                isStarting={isStarting}
              />
            ))}
          </div>
        </div>
      )}

      {/* External Score Dialog */}
      <ExternalLogDialog
        open={!!logDialogSet}
        onOpenChange={(open) => !open && setLogDialogSet(null)}
        set={logDialogSet}
      />
    </Container>
  )
}
