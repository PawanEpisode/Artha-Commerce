import {
  Alert,
  Badge,
  Button,
  ButtonLink,
  Card,
  Container,
  Play,
  Skeleton,
  Sparkles,
  toast,
} from '@artha/design-system'
import { Link, useNavigate } from '@tanstack/react-router'
import { useEffect, useState } from 'react'

import { ExternalLogDialog } from '../components/ExternalLogDialog'
import { McqSubjectCard } from '../components/McqSubjectCard'
import { SetCard } from '../components/SetCard'
import { getMcqHome, listMcqSets, startQuickPractice, startSetPractice } from '../lib/api'
import type { McqHomeData, McqSetCard } from '../lib/types'

export function McqHomeContainer() {
  const navigate = useNavigate()
  const [data, setData] = useState<McqHomeData | null>(null)
  const [featuredSets, setFeaturedSets] = useState<McqSetCard[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [isStarting, setIsStarting] = useState(false)
  const [logDialogSet, setLogDialogSet] = useState<McqSetCard | null>(null)

  useEffect(() => {
    async function load() {
      try {
        const [homeData, sets] = await Promise.all([getMcqHome(), listMcqSets({})])
        setData(homeData)
        setFeaturedSets(sets)
      } catch (err: unknown) {
        toast.error(err instanceof Error ? err.message : 'Failed to load MCQ Bank')
      } finally {
        setIsLoading(false)
      }
    }
    load()
  }, [])

  async function handleStartSuggested() {
    if (!data?.suggestion) return
    try {
      setIsStarting(true)
      const res = await startQuickPractice({
        chapter_id: data.suggestion.chapter_id,
        subject_key: data.suggestion.subject_key,
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
      toast.error(err instanceof Error ? err.message : 'Could not start practice set')
      setIsStarting(false)
    }
  }

  if (isLoading) {
    return (
      <Container className="space-y-6 py-8">
        <Skeleton className="h-10 w-64" />
        <Skeleton className="h-40 w-full" />
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          <Skeleton className="h-32 w-full" />
          <Skeleton className="h-32 w-full" />
          <Skeleton className="h-32 w-full" />
        </div>
      </Container>
    )
  }

  return (
    <Container className="space-y-8 py-8">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-2xl font-bold tracking-tight text-foreground sm:text-3xl">MCQ Bank</h1>
            <Badge variant="outline" className="text-xs uppercase">
              {data?.course} {data?.level}
            </Badge>
          </div>
          <p className="mt-1 text-sm text-muted-foreground">
            Targeted multiple-choice practice matching the authentic ICMAI Syllabus 2022 examination scheme.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <ButtonLink asChild variant="outline" size="sm">
            <Link to="/app/pyq">Past Papers (PYQ)</Link>
          </ButtonLink>
          <ButtonLink asChild variant="outline" size="sm">
            <Link to="/app/questions">Question Bank</Link>
          </ButtonLink>
        </div>
      </div>

      {/* Suggested Quick Sprint Banner */}
      {data?.suggestion && (
        <Card className="relative overflow-hidden border-primary/30 bg-primary/5 p-6 dark:bg-primary/10">
          <div className="flex flex-wrap items-center justify-between gap-4">
            <div className="max-w-xl space-y-2">
              <div className="flex items-center gap-2">
                <Sparkles className="h-4 w-4 text-primary" />
                <span className="text-xs font-semibold tracking-wide text-primary uppercase">
                  Recommended Practice Sprint
                </span>
              </div>
              <h3 className="text-lg font-semibold text-foreground">
                High-Yield Review: {data.suggestion.chapter_key}
              </h3>
              <p className="text-xs text-muted-foreground">{data.suggestion.reasons.join(' · ')}</p>
            </div>

            <Button
              size="default"
              disabled={isStarting}
              onClick={handleStartSuggested}
              className="gap-2 font-semibold shadow"
            >
              <Play className="h-4 w-4 fill-current" />
              Start 10 MCQs
            </Button>
          </div>
        </Card>
      )}

      {/* Open Sessions Strip */}
      {data?.open_sessions && data.open_sessions.length > 0 && (
        <div className="space-y-3">
          <h2 className="text-sm font-semibold tracking-wider text-muted-foreground uppercase">
            Resume Practice Session
          </h2>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {data.open_sessions.map((s) => (
              <Card key={s.id} className="flex items-center justify-between p-4">
                <div>
                  <div className="text-sm font-medium text-foreground">{s.title}</div>
                  <div className="text-xs text-muted-foreground">
                    {s.question_count} questions · {s.mode}
                  </div>
                </div>
                <ButtonLink asChild size="sm" variant="outline">
                  <Link to="/app/practice/session/$id" params={{ id: s.id }}>
                    Resume
                  </Link>
                </ButtonLink>
              </Card>
            ))}
          </div>
        </div>
      )}

      {/* Subjects Grid */}
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-semibold text-foreground">Browse by Subject</h2>
        </div>

        {data?.subjects && data.subjects.length > 0 ? (
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {data.subjects.map((sub) => (
              <McqSubjectCard key={sub.code} subject={sub} />
            ))}
          </div>
        ) : (
          <Alert>No subjects configured for current syllabus enrollment.</Alert>
        )}
      </div>

      {/* Featured MCQ Practice Sets */}
      {featuredSets.length > 0 && (
        <div className="space-y-4 border-t pt-4">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-lg font-semibold text-foreground">Curated Practice Sets & ICMAI Booklets</h2>
              <p className="text-xs text-muted-foreground">
                Platform-hosted interactive sprints and official ICMAI Directorate of Studies question banks.
              </p>
            </div>
          </div>

          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {featuredSets.map((s) => (
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
