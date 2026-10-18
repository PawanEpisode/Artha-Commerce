import { Badge, Button, Eye } from '@artha/design-system'

import { RichText } from '~/lib/richtext'

import { numericKeyText, QUESTION_TEXT_CLASS } from '../lib/labels'
import type { ReviewQuestion } from '../lib/types'
import { QuestionOptionsList } from './QuestionOptionsList'

interface QuestionAnswerPanelProps {
  review: ReviewQuestion
  /** Show the correct option(s), the explanation and the references. */
  revealed: boolean
  onReveal: () => void
}

/** One question in full: stem, options, and (once asked for) the answer with its explanation. Props only. */
export function QuestionAnswerPanel({ review, revealed, onReveal }: QuestionAnswerPanelProps) {
  const options = review.options ?? []
  const correctIds = review.correct_option_ids ?? []
  const numericKey = review.kind === 'numeric' ? numericKeyText(review.numeric_key) : null
  const hasAnswer = correctIds.length > 0 || numericKey !== null

  return (
    <div className="space-y-3">
      <RichText markdown={review.stem_md} profile="question" className={QUESTION_TEXT_CLASS} />

      {review.kind === 'mcq_multi' && (
        <p className="text-xs text-muted-foreground">
          More than one option can be correct{revealed && correctIds.length > 0 ? ` (${correctIds.length} here)` : ''}.
        </p>
      )}

      {options.length > 0 && (
        <QuestionOptionsList options={options} correctOptionIds={correctIds} revealed={revealed} />
      )}

      {revealed && numericKey !== null && (
        <div className="rounded-md border border-border bg-muted/40 px-3 py-2">
          <p className="text-xs text-muted-foreground">Correct numerical value</p>
          <p className="text-base font-semibold text-foreground tabular-nums">{numericKey}</p>
        </div>
      )}

      {!revealed ? (
        <Button size="sm" variant="outline" onClick={onReveal}>
          <Eye aria-hidden className="size-3.5" />
          Show answer
        </Button>
      ) : (
        <div className="space-y-2" aria-live="polite">
          {!hasAnswer && (
            <p className="text-xs text-muted-foreground">The answer key for this question is not available yet.</p>
          )}
          {review.explanation_md ? (
            <div className="space-y-1 border-t border-border pt-2">
              <h3 className="text-[11px] font-medium tracking-wide text-muted-foreground uppercase">Explanation</h3>
              <RichText markdown={review.explanation_md} profile="question" className={QUESTION_TEXT_CLASS} />
            </div>
          ) : null}
          {review.reference_labels && review.reference_labels.length > 0 ? (
            <div className="flex flex-wrap items-center gap-1.5">
              <span className="text-xs text-muted-foreground">References:</span>
              {review.reference_labels.map((ref) => (
                <Badge key={ref} variant="outline">
                  {ref}
                </Badge>
              ))}
            </div>
          ) : null}
        </div>
      )}
    </div>
  )
}
