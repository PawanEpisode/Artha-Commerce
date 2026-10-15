import { Badge, ButtonLink, Card } from '@artha/design-system'
import { Link } from '@tanstack/react-router'

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
    <div className="mx-auto max-w-4xl space-y-8 px-4 py-12">
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
        <h1 className="font-display text-3xl font-bold tracking-tight text-foreground sm:text-4xl">
          {chapterName} Questions & Practice
        </h1>
        <p className="text-base text-muted-foreground">
          Past exam questions, RTP, MTP, and study questions for {subjectName} ({courseName} {levelName}).
        </p>
      </div>

      {/* Primary CTA */}
      <Card className="flex flex-col items-start justify-between gap-4 border-primary/30 bg-primary/5 p-6 sm:flex-row sm:items-center dark:bg-primary/10">
        <div>
          <h2 className="text-base font-bold text-foreground">Want interactive practice with instant feedback?</h2>
          <p className="text-sm text-muted-foreground">
            Solve questions timed or untimed, see step-by-step solutions, and track your syllabus coverage.
          </p>
        </div>
        <ButtonLink asChild size="lg">
          <Link to="/login" search={{ next: `/app/practice/new?subject=${subjectSlug}&chapter=${chapterSlug}` }}>
            Start practising
          </Link>
        </ButtonLink>
      </Card>

      {/* Question List */}
      <div className="space-y-4">
        <h2 className="text-xl font-bold text-foreground">Sample Questions ({questions.length})</h2>

        {questions.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            Questions for this chapter are currently being curated by our editorial team.
          </p>
        ) : (
          <div className="space-y-4">
            {questions.map((q, idx) => (
              <Card key={q.id} className="space-y-3 p-5">
                <div className="flex flex-wrap items-center justify-between gap-2 text-xs">
                  <div className="flex items-center gap-2">
                    <span className="font-bold text-muted-foreground">Q{idx + 1}</span>
                    <Badge variant="outline">{q.kind.replace('_', ' ')}</Badge>
                    <span className="text-muted-foreground">•</span>
                    <span className="font-medium">
                      {q.marks} {q.marks === 1 ? 'mark' : 'marks'}
                    </span>
                  </div>
                  {q.source_name && (
                    <span className="text-muted-foreground">
                      Source: {q.source_name} {q.source_year ?? ''}
                    </span>
                  )}
                </div>

                <p className="text-sm leading-relaxed text-foreground">{q.stem_head}</p>
              </Card>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
