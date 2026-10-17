import {
  Alert,
  Badge,
  Button,
  ButtonLink,
  Card,
  DataTable,
  Page,
  PageHeader,
  Play,
  Skeleton,
  Sparkles,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
  toastApiError,
} from '@artha/design-system'
import { Link, useNavigate } from '@tanstack/react-router'
import { useEffect, useState } from 'react'

import { ExternalLogDialog } from '../components/ExternalLogDialog'
import { SetsTable } from '../components/SetsTable'
import { SubjectsTable } from '../components/SubjectsTable'
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
        toastApiError(err, 'Failed to load MCQ Bank')
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
      toastApiError(err, 'Could not start practice set')
      setIsStarting(false)
    }
  }

  if (isLoading) {
    return (
      <Page>
        <div role="status" aria-busy="true" aria-label="Loading MCQ Bank" className="space-y-3">
          <Skeleton className="h-8 w-64" />
          <Skeleton className="h-20 w-full" />
          <Skeleton className="h-48 w-full" />
        </div>
      </Page>
    )
  }

  return (
    <Page>
      <PageHeader
        title={
          <span className="inline-flex items-center gap-2">
            MCQ Bank
            {data?.course || data?.level ? (
              <Badge variant="outline" className="uppercase">
                {data?.course} {data?.level}
              </Badge>
            ) : null}
          </span>
        }
        description="Targeted multiple-choice practice matching the authentic ICMAI Syllabus 2022 examination scheme."
        actions={
          <>
            <ButtonLink asChild variant="outline" size="sm">
              <Link to="/app/pyq">Past Papers (PYQ)</Link>
            </ButtonLink>
            <ButtonLink asChild variant="outline" size="sm">
              <Link to="/app/questions">Question Bank</Link>
            </ButtonLink>
          </>
        }
      />

      {data?.suggestion && (
        <Card className="border-primary/30 bg-primary/5 p-4 dark:bg-primary/10">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="max-w-xl space-y-1">
              <div className="flex items-center gap-1.5">
                <Sparkles aria-hidden className="size-3.5 text-primary" />
                <span className="text-[11px] font-medium tracking-wide text-primary uppercase">
                  Recommended Practice Sprint
                </span>
              </div>
              <h2 className="text-sm font-semibold text-foreground">
                High-Yield Review: {data.suggestion.chapter_key}
              </h2>
              <p className="text-xs text-muted-foreground">{data.suggestion.reasons.join(' · ')}</p>
            </div>

            <Button disabled={isStarting} onClick={handleStartSuggested}>
              <Play aria-hidden className="size-3.5 fill-current" />
              Start 10 MCQs
            </Button>
          </div>
        </Card>
      )}

      {data?.open_sessions && data.open_sessions.length > 0 && (
        <section className="space-y-2">
          <h2 className="text-sm font-semibold text-foreground">Resume practice session</h2>
          <DataTable>
            <TableHeader>
              <TableRow className="hover:bg-transparent">
                <TableHead>Session</TableHead>
                <TableHead className="hidden sm:table-cell">Mode</TableHead>
                <TableHead className="text-right">Questions</TableHead>
                <TableHead className="text-right">
                  <span className="sr-only">Action</span>
                </TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {data.open_sessions.map((s) => (
                <TableRow key={s.id}>
                  <TableCell className="max-w-56 truncate font-medium">{s.title}</TableCell>
                  <TableCell className="hidden text-muted-foreground capitalize sm:table-cell">
                    {s.mode.replace(/_/g, ' ')}
                  </TableCell>
                  <TableCell className="text-right tabular-nums">{s.question_count}</TableCell>
                  <TableCell className="text-right">
                    <ButtonLink asChild size="sm" variant="outline">
                      <Link to="/app/practice/session/$id" params={{ id: s.id }}>
                        Resume
                      </Link>
                    </ButtonLink>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </DataTable>
        </section>
      )}

      <section className="space-y-2">
        <h2 className="text-sm font-semibold text-foreground">Browse by subject</h2>
        {data?.subjects && data.subjects.length > 0 ? (
          <SubjectsTable subjects={data.subjects} />
        ) : (
          <Alert>No subjects configured for current syllabus enrollment.</Alert>
        )}
      </section>

      {featuredSets.length > 0 && (
        <section className="space-y-2">
          <div>
            <h2 className="text-sm font-semibold text-foreground">Curated practice sets and ICMAI booklets</h2>
            <p className="text-xs text-muted-foreground">
              Platform-hosted interactive sprints and official ICMAI Directorate of Studies question banks.
            </p>
          </div>

          <SetsTable
            sets={featuredSets}
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
