import { Badge, Bookmark, Card, CircleAlert, CircleCheck, CircleX, ShieldCheck } from '@artha/design-system'
import { Link } from '@tanstack/react-router'

import type { QuestionCardData } from '../lib/types'

interface QuestionCardProps {
  question: QuestionCardData
  showOverlay?: boolean
  className?: string
}

const kindLabels: Record<string, string> = {
  mcq_single: 'MCQ Single',
  mcq_multi: 'MCQ Multi',
  true_false: 'True / False',
  numeric: 'Numeric',
  case_study: 'Case Study',
  long_form: 'Long Form',
  practical: 'Practical',
}

export function QuestionCard({ question, showOverlay = true, className }: QuestionCardProps) {
  const kindLabel = kindLabels[question.kind] || question.kind

  return (
    <Card className={className}>
      <Link
        to="/app/questions/$id"
        params={{ id: question.id }}
        className="block space-y-3 p-4 transition-colors hover:bg-muted/30 focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
      >
        <div className="flex flex-wrap items-center justify-between gap-2 text-xs">
          <div className="flex flex-wrap items-center gap-1.5">
            <Badge variant="outline" className="font-semibold">
              {kindLabel}
            </Badge>
            <span className="text-muted-foreground">•</span>
            <span className="font-medium text-foreground">
              {question.marks} {question.marks === 1 ? 'mark' : 'marks'}
            </span>
            {question.source_name && (
              <>
                <span className="text-muted-foreground">•</span>
                <span className="max-w-40 truncate text-muted-foreground">
                  {question.source_name}
                  {question.source_year ? ` ${question.source_year}` : ''}
                </span>
              </>
            )}
          </div>

          <div className="flex items-center gap-2">
            {question.is_verified && (
              <span className="inline-flex items-center gap-1 text-xs font-medium text-emerald-700 dark:text-emerald-400">
                <ShieldCheck aria-hidden className="size-3.5" />
                Verified
              </span>
            )}
            {question.is_bookmarked && (
              <Bookmark aria-label="Bookmarked" className="size-3.5 fill-amber-500 text-amber-500" />
            )}
          </div>
        </div>

        <p className="line-clamp-3 text-sm leading-relaxed font-medium text-foreground">{question.stem_head}</p>

        <div className="flex flex-wrap items-center justify-between gap-2 border-t border-border/60 pt-2 text-xs text-muted-foreground">
          <div className="flex items-center gap-2">
            <span>Diff {question.difficulty}/5</span>
            {question.nature && (
              <>
                <span>•</span>
                <span className="capitalize">{question.nature}</span>
              </>
            )}
          </div>

          {showOverlay && question.last_result && (
            <div className="flex items-center gap-1 font-medium">
              <span>You:</span>
              {question.last_result === 'correct' && (
                <span className="inline-flex items-center gap-0.5 text-emerald-600 dark:text-emerald-400">
                  <CircleCheck className="size-3.5" /> Correct
                </span>
              )}
              {question.last_result === 'incorrect' && (
                <span className="inline-flex items-center gap-0.5 text-destructive">
                  <CircleX className="size-3.5" /> Incorrect
                </span>
              )}
              {question.last_result === 'skipped' && (
                <span className="inline-flex items-center gap-0.5 text-muted-foreground">
                  <CircleAlert className="size-3.5" /> Skipped
                </span>
              )}
            </div>
          )}
        </div>
      </Link>
    </Card>
  )
}
