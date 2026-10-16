import { Button, buttonVariants, X } from '@artha/design-system'
import { Link } from '@tanstack/react-router'

export interface SetupCard {
  key: string
  title: string
  description: string
}

/** One card per skipped step, each with a way back into that step and a way to put it away. */
export function SetupCards({ cards, onDismiss }: { cards: SetupCard[]; onDismiss: (key: string) => void }) {
  return (
    <ul className="grid gap-2 md:grid-cols-2 xl:grid-cols-3">
      {cards.map((card) => (
        <li
          key={card.key}
          className="flex items-start justify-between gap-2 rounded-lg border border-border bg-card p-3"
        >
          <div className="min-w-0 space-y-1.5">
            <p className="font-medium">{card.title}</p>
            <p className="text-[13px] text-muted-foreground">{card.description}</p>
            <Link
              to="/app/onboarding"
              search={{ step: card.key }}
              className={buttonVariants({ variant: 'outline', size: 'sm' })}
            >
              Finish <span className="sr-only">{card.title}</span>
            </Link>
          </div>
          <Button
            variant="ghost"
            size="icon-sm"
            className="-mt-1 -mr-1 shrink-0"
            onClick={() => onDismiss(card.key)}
            aria-label={`Hide ${card.title}`}
          >
            <X aria-hidden />
          </Button>
        </li>
      ))}
    </ul>
  )
}
