import { Badge, Button, ButtonLink, Card, Clock, Play } from '@artha/design-system'
import { Link } from '@tanstack/react-router'

import type { PyqPaperCard } from '../lib/types'

interface PaperCardProps {
  paper: PyqPaperCard
  onStartPractice?: (paperId: string) => void
  isStarting?: boolean
  className?: string
}

const termDisplayNames: Record<string, string> = {
  june: 'June',
  dec: 'December',
  may: 'May',
  nov: 'November',
}

export function PaperCard({ paper, onStartPractice, isStarting, className }: PaperCardProps) {
  const parts = paper.term_code.split('_')
  const termName = parts[0] ? termDisplayNames[parts[0]] || parts[0].toUpperCase() : paper.term_code
  const termYear = parts[1] || ''

  const isCurrentScheme = paper.syllabus_status === 'current'
  const isInteractive = paper.delivery === 'digitised_interactive'

  return (
    <Card
      className={`flex flex-col justify-between overflow-hidden p-5 transition-shadow hover:shadow-md ${className ?? ''}`}
    >
      <div className="space-y-3">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div className="flex flex-wrap items-center gap-1.5">
            <Badge variant="outline" className="font-semibold text-primary">
              {termName} {termYear}
            </Badge>
            <Badge variant="default" className="font-mono text-xs uppercase">
              {paper.paper_code || paper.subject_key}
            </Badge>
          </div>

          <div className="flex items-center gap-1.5 text-xs">
            {isCurrentScheme ? (
              <span className="inline-flex items-center rounded-full bg-emerald-50 px-2 py-0.5 font-medium text-emerald-700 dark:bg-emerald-950/40 dark:text-emerald-300">
                2022 Syllabus
              </span>
            ) : (
              <span className="inline-flex items-center rounded-full bg-amber-50 px-2 py-0.5 font-medium text-amber-700 dark:bg-amber-950/40 dark:text-amber-300">
                Mapped Syllabus
              </span>
            )}
          </div>
        </div>

        <div>
          <Link
            to="/app/pyq/papers/$id"
            params={{ id: paper.id }}
            className="group block text-base font-semibold text-foreground transition-colors hover:text-primary"
          >
            {paper.title}
          </Link>
          <p className="mt-0.5 text-xs text-muted-foreground capitalize">
            {paper.course_code.toUpperCase()} • {paper.level_code.replace('_', ' ').toUpperCase()}
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-3 border-t border-border/50 pt-1 text-xs text-muted-foreground">
          <span className="font-medium text-foreground">{paper.total_marks} Marks</span>
          <span>•</span>
          <span className="inline-flex items-center gap-1">
            <Clock className="size-3" />
            {paper.duration_minutes ? `${paper.duration_minutes} mins` : '3 hours'}
          </span>
          <span>•</span>
          <span>{paper.question_count} Questions</span>
        </div>
      </div>

      <div className="mt-5 flex items-center justify-between gap-2 border-t border-border pt-3">
        <ButtonLink asChild variant="outline" size="sm">
          <Link to="/app/pyq/papers/$id" params={{ id: paper.id }}>
            View Paper
          </Link>
        </ButtonLink>

        {onStartPractice && (
          <Button size="sm" onClick={() => onStartPractice(paper.id)} disabled={isStarting} className="gap-1.5">
            <Play className="size-3.5 fill-current" />
            {isStarting ? 'Starting...' : isInteractive ? 'Simulate Exam' : 'Practise Paper'}
          </Button>
        )}
      </div>
    </Card>
  )
}
