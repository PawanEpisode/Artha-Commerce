import { ArrowLeft, Badge, ButtonLink, Container, Skeleton, toast } from '@artha/design-system'
import { Link, useNavigate } from '@tanstack/react-router'
import { useEffect, useState } from 'react'

import { ChapterTileGrid } from '../components/ChapterTileGrid'
import { getSubjectTiles, startQuickPractice } from '../lib/api'
import type { ChapterTile } from '../lib/types'

interface McqSubjectContainerProps {
  subjectKey: string
}

export function McqSubjectContainer({ subjectKey }: McqSubjectContainerProps) {
  const navigate = useNavigate()
  const [chapters, setChapters] = useState<ChapterTile[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [isStarting, setIsStarting] = useState(false)

  useEffect(() => {
    async function load() {
      try {
        const tiles = await getSubjectTiles(subjectKey)
        setChapters(tiles)
      } catch (err: unknown) {
        toast.error(err instanceof Error ? err.message : 'Failed to load subject chapters')
      } finally {
        setIsLoading(false)
      }
    }
    load()
  }, [subjectKey])

  async function handleQuickPractice(chapterId: string) {
    try {
      setIsStarting(true)
      const res = await startQuickPractice({
        chapter_id: chapterId,
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

  const totalAvailable = chapters.reduce((acc, c) => acc + c.available, 0)
  const totalAttempted = chapters.reduce((acc, c) => acc + (c.available - c.unseen), 0)

  if (isLoading) {
    return (
      <Container className="space-y-6 py-8">
        <Skeleton className="h-6 w-32" />
        <Skeleton className="h-10 w-64" />
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          <Skeleton className="h-44 w-full" />
          <Skeleton className="h-44 w-full" />
          <Skeleton className="h-44 w-full" />
        </div>
      </Container>
    )
  }

  const subjectTitle = subjectKey
    .split('-')
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(' ')

  return (
    <Container className="space-y-8 py-8">
      {/* Breadcrumb & Navigation */}
      <div className="space-y-4">
        <ButtonLink
          asChild
          variant="ghost"
          size="sm"
          className="-ml-2 gap-1.5 text-xs text-muted-foreground hover:text-foreground"
        >
          <Link to="/app/mcq">
            <ArrowLeft className="h-3.5 w-3.5" />
            Back to MCQ Bank
          </Link>
        </ButtonLink>

        <div className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-2xl font-bold tracking-tight text-foreground sm:text-3xl">{subjectTitle}</h1>
              <Badge variant="outline" className="font-mono text-xs uppercase">
                {subjectKey}
              </Badge>
            </div>
            <p className="mt-1 text-sm text-muted-foreground">
              {totalAvailable} total MCQs across {chapters.length} syllabus chapters ({totalAttempted} attempted).
            </p>
          </div>
        </div>
      </div>

      {/* Chapters Grid */}
      <div className="space-y-4">
        <ChapterTileGrid
          chapters={chapters}
          subjectKey={subjectKey}
          onQuickPractice={handleQuickPractice}
          isStarting={isStarting}
        />
      </div>
    </Container>
  )
}
