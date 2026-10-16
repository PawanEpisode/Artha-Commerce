import { Button, Check, Layers, toast } from '@artha/design-system'
import { Link } from '@tanstack/react-router'

import { useCardFromQuestion } from '../hooks/useHistory'
import { useOnlineStatus, useRecallEnabled } from '../hooks/useRecallBasics'
import { errorText } from '../lib/errors'

interface Props {
  questionId: string
  versionId: string
  /** Called with the new card's id, so the question screen can show "Card made" without knowing about recall. */
  onMade?: (cardId: string, existing: boolean) => void
}

/**
 * "Make a card from this question": for the question bank (F-06) to put on a wrong answer. The card's text is the bank's own
 * explanation and source, made on the server. Hidden while recall is off for her.
 */
export function QuestionCardButton({ questionId, versionId, onMade }: Props) {
  const on = useRecallEnabled()
  const online = useOnlineStatus()
  const make = useCardFromQuestion(questionId, versionId)
  if (!on) return null
  const card = make.data
  if (card) {
    return (
      <p className="flex flex-wrap items-center gap-2 text-sm">
        <Check aria-hidden className="size-4 text-primary" />
        {card.existing ? 'You already have a card for this question.' : 'Card made.'}
        <Link className="font-medium underline" to="/app/recall/cards/$cardId" params={{ cardId: card.card_id }}>
          Open the card
        </Link>
      </p>
    )
  }
  return (
    <div className="space-y-1">
      <Button
        variant="outline"
        size="sm"
        className="w-full justify-start"
        loading={make.isPending}
        disabled={!online}
        onClick={() =>
          make.mutate(undefined, {
            onSuccess: (r) => onMade?.(r.card_id, r.existing),
            onError: (e) => toast.error(errorText(e, 'We could not make a card from this question. Please try again.')),
          })
        }
      >
        <Layers aria-hidden /> Make a card from this
      </Button>
      {!online ? <p className="text-xs text-muted-foreground">This needs the internet.</p> : null}
    </div>
  )
}
