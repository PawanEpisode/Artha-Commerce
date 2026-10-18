import { Check, CircleX } from '@artha/design-system'

import { RichText } from '~/lib/richtext'

import { QUESTION_TEXT_CLASS } from '../lib/labels'
import type { ReviewOption } from '../lib/types'

interface QuestionOptionsListProps {
  options: ReviewOption[]
  correctOptionIds: string[]
  /** Mark the right and the wrong options. Off, every option looks the same (answer still hidden). */
  revealed: boolean
}

/**
 * The options of one question as lettered rows. Right and wrong are said in words and icons as well as colour. With no
 * answer key (an empty `correctOptionIds`) nothing is marked wrong, because nothing is known to be.
 */
export function QuestionOptionsList({ options, correctOptionIds, revealed }: QuestionOptionsListProps) {
  const hasAnswerKey = correctOptionIds.length > 0
  return (
    <ul className="space-y-1.5">
      {options.map((opt, idx) => {
        const isCorrect = revealed && correctOptionIds.includes(opt.id)
        const isWrong = revealed && hasAnswerKey && !isCorrect
        const letter = String.fromCharCode(65 + idx)
        return (
          <li
            key={opt.id}
            className={`flex min-h-10 items-center gap-2.5 rounded-md border px-2.5 py-1.5 ${
              isCorrect ? 'border-success-border bg-success-bg' : 'border-border bg-card'
            }`}
          >
            <span
              aria-hidden
              className={`grid size-6 shrink-0 place-items-center rounded-md text-xs font-semibold ${
                isCorrect ? 'border border-success-border bg-card text-success-fg' : 'bg-muted text-foreground'
              }`}
            >
              {letter}
            </span>
            <div className="min-w-0 flex-1">
              <span className="sr-only">Option {letter}. </span>
              <RichText markdown={opt.body_md} profile="question" className={QUESTION_TEXT_CLASS} />
            </div>
            {isCorrect && (
              <span className="inline-flex shrink-0 items-center gap-1 text-xs font-medium text-success-fg">
                <Check aria-hidden className="size-3.5" /> Correct
              </span>
            )}
            {isWrong && (
              <span className="inline-flex shrink-0 items-center gap-1 text-xs text-muted-foreground">
                <CircleX aria-hidden className="size-3.5" /> Incorrect
              </span>
            )}
          </li>
        )
      })}
    </ul>
  )
}
