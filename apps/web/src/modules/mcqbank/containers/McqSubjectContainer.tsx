import { Badge, EmptyState, Page, PageHeader, Skeleton, toastApiError } from '@artha/design-system'
import { Link, useNavigate } from '@tanstack/react-router'
import { useEffect, useState } from 'react'

import { ChaptersTable } from '../components/ChaptersTable'
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
        toastApiError(err, 'Failed to load subject chapters')
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
        feedback_policy: 'instant',
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

  const totalAvailable = chapters.reduce((acc, c) => acc + c.available, 0)
  const totalAttempted = chapters.reduce((acc, c) => acc + (c.available - c.unseen), 0)

  if (isLoading) {
    return (
      <Page>
        <div role="status" aria-busy="true" aria-label="Loading chapters" className="space-y-3">
          <Skeleton className="h-8 w-64" />
          <Skeleton className="h-48 w-full" />
        </div>
      </Page>
    )
  }

  const subjectTitle = subjectKey
    .split('-')
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(' ')

  return (
    <Page>
      <PageHeader
        eyebrow={
          <Link to="/app/mcq" className="hover:underline">
            MCQ Bank
          </Link>
        }
        title={
          <span className="inline-flex items-center gap-2">
            {subjectTitle}
            <Badge variant="outline" className="font-mono uppercase">
              {subjectKey}
            </Badge>
          </span>
        }
        description={`${totalAvailable} total MCQs across ${chapters.length} syllabus chapters (${totalAttempted} attempted).`}
      />

      {chapters.length === 0 ? (
        <EmptyState title="No chapters found for this subject." />
      ) : (
        <ChaptersTable
          chapters={chapters}
          subjectKey={subjectKey}
          onQuickPractice={handleQuickPractice}
          isStarting={isStarting}
        />
      )}
    </Page>
  )
}
