import { ButtonLink, Card, Container } from '@artha/design-system'
import { Link } from '@tanstack/react-router'

import { QuestionTable } from '../components/QuestionTable'
import type { QuestionCardData } from '../lib/types'

interface PublicChapterQuestionsContainerProps {
  courseName: string
  levelName: string
  subjectName: string
  chapterName: string
  courseSlug: string
  levelSlug: string
  subjectSlug: string
  chapterSlug: string
  questions: QuestionCardData[]
}

export function PublicChapterQuestionsContainer({
  courseName,
  levelName,
  subjectName,
  chapterName,
  courseSlug,
  levelSlug,
  subjectSlug,
  chapterSlug,
  questions,
}: PublicChapterQuestionsContainerProps) {
  return (
    <Container className="space-y-6 py-10">
      {/* Breadcrumb / Context */}
      <nav aria-label="Breadcrumb" className="text-xs text-muted-foreground">
        <ol className="flex flex-wrap items-center gap-1.5">
          <li>
            <Link to="/courses" className="hover:underline">
              Courses
            </Link>
          </li>
          <li>/</li>
          <li>
            <Link to="/courses/$course" params={{ course: courseSlug }} className="hover:underline">
              {courseName}
            </Link>
          </li>
          <li>/</li>
          <li>
            <Link
              to="/courses/$course/$level"
              params={{ course: courseSlug, level: levelSlug }}
              className="hover:underline"
            >
              {levelName}
            </Link>
          </li>
          <li>/</li>
          <li>
            <Link
              to="/courses/$course/$level/$subject"
              params={{ course: courseSlug, level: levelSlug, subject: subjectSlug }}
              className="hover:underline"
            >
              {subjectName}
            </Link>
          </li>
          <li>/</li>
          <li>
            <Link
              to="/courses/$course/$level/$subject/$chapter"
              params={{ course: courseSlug, level: levelSlug, subject: subjectSlug, chapter: chapterSlug }}
              className="hover:underline"
            >
              {chapterName}
            </Link>
          </li>
          <li>/</li>
          <li className="font-semibold text-foreground">Questions</li>
        </ol>
      </nav>

      {/* Header */}
      <div className="space-y-3">
        <h1 className="font-display text-3xl font-semibold tracking-tight text-foreground sm:text-4xl">
          {chapterName} Questions & Practice
        </h1>
        <p className="text-base text-muted-foreground">
          Past exam questions, RTP, MTP, and study questions for {subjectName} ({courseName} {levelName}).
        </p>
      </div>

      {/* Primary CTA */}
      <Card className="flex flex-col items-start justify-between gap-3 border-primary/30 bg-primary/5 p-4 sm:flex-row sm:items-center dark:bg-primary/10">
        <div>
          <h2 className="text-base font-semibold text-foreground">Want interactive practice with instant feedback?</h2>
          <p className="text-sm text-muted-foreground">
            Solve questions timed or untimed, see step-by-step solutions, and track your syllabus coverage.
          </p>
        </div>
        <ButtonLink asChild>
          <Link to="/login" search={{ next: `/app/practice/new?subject=${subjectSlug}&chapter=${chapterSlug}` }}>
            Start practising
          </Link>
        </ButtonLink>
      </Card>

      {/* Question List */}
      <div className="space-y-3">
        <h2 className="text-sm font-semibold text-foreground">Sample Questions ({questions.length})</h2>

        {questions.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            Questions for this chapter are currently being curated by our editorial team.
          </p>
        ) : (
          <QuestionTable questions={questions} showOverlay={false} linked={false} />
        )}
      </div>
    </Container>
  )
}
