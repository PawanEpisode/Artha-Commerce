import { Badge, Button, ButtonLink, Card, Clock, Play } from '@artha/design-system'
import { Link } from '@tanstack/react-router'

import type { McqSetCard } from '../lib/types'

interface SetCardProps {
  set: McqSetCard
  onStartPractice?: (slug: string) => void
  onOpenExternalLog?: (set: McqSetCard) => void
  isStarting?: boolean
  className?: string
}

export function SetCard({ set, onStartPractice, onOpenExternalLog, isStarting, className }: SetCardProps) {
  const isHosted = set.delivery === 'hosted'
  const isLinkOut = set.delivery === 'link_out'

  return (
    <Card
      className={`flex flex-col justify-between overflow-hidden p-5 transition-shadow hover:shadow-md ${className ?? ''}`}
    >
      <div className="space-y-3">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div className="flex flex-wrap items-center gap-1.5">
            {set.featured && (
              <Badge variant="default" className="text-xs">
                Featured
              </Badge>
            )}
            <Badge variant="outline" className="text-xs uppercase">
              {set.set_kind.replace('_', ' ')}
            </Badge>
            {set.verified && (
              <Badge variant="outline" className="text-xs text-emerald-700 dark:text-emerald-300">
                Verified
              </Badge>
            )}
          </div>

          <div className="flex items-center gap-2 text-xs text-muted-foreground">
            {set.est_minutes > 0 && (
              <span className="flex items-center gap-1">
                <Clock className="h-3 w-3" />
                {set.est_minutes}m
              </span>
            )}
            <span>{set.question_count} MCQs</span>
          </div>
        </div>

        <div>
          <Link
            to="/app/mcq/sets/$slug"
            params={{ slug: set.slug }}
            className="group block text-base font-semibold text-foreground transition-colors hover:text-primary"
          >
            {set.title}
          </Link>
          {set.description && <p className="mt-1 line-clamp-2 text-xs text-muted-foreground">{set.description}</p>}
        </div>

        {set.source_name && (
          <div className="text-xs text-muted-foreground">
            Source: <span className="font-medium text-foreground">{set.source_name}</span>
          </div>
        )}
      </div>

      <div className="mt-4 flex items-center justify-between gap-2 border-t pt-4">
        {isHosted ? (
          <Button
            size="sm"
            className="w-full gap-1.5 text-xs font-semibold"
            disabled={isStarting}
            onClick={() => onStartPractice?.(set.slug)}
          >
            <Play className="h-3.5 w-3.5 fill-current" />
            Practice Online
          </Button>
        ) : isLinkOut ? (
          <div className="flex w-full items-center gap-2">
            {set.source_url && (
              <ButtonLink
                size="sm"
                variant="outline"
                href={set.source_url}
                target="_blank"
                rel="noreferrer"
                className="flex-1 text-xs"
              >
                Open ICMAI PDF
              </ButtonLink>
            )}
            <Button size="sm" variant="default" className="flex-1 text-xs" onClick={() => onOpenExternalLog?.(set)}>
              Log Offline Score
            </Button>
          </div>
        ) : null}
      </div>
    </Card>
  )
}
