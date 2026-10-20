import { Badge, Bookmark, Button, Card, Checkbox, cn } from '@artha/design-system'
import { Link } from '@tanstack/react-router'

import { useCardActions } from '../hooks/useCardActions'
import type { MyCard } from '../lib/types'
import { ApplicabilityTag } from './ApplicabilityTag'
import { ChangeTypeBadge } from './ChangeTypeBadge'
import { DiffPair } from './DiffPair'
import { OfficialPdfButton } from './OfficialPdfButton'
import { ReportDialog } from './ReportDialog'

interface Props {
  card: MyCard
  targetTerm?: string | null
  className?: string
}

export function ChangeCard({ card, targetTerm, className }: Props) {
  const { toggleReviewed, toggleSaved, isReviewing, isSaving } = useCardActions()

  const primaryMapping = card.mappings.find((m) => m.is_primary) ?? card.mappings[0]

  return (
    <Card
      className={cn(
        'group border transition-shadow hover:shadow-sm',
        card.is_reviewed && 'border-muted bg-muted/20',
        className,
      )}
    >
      <div className="p-4 sm:p-5">
        {/* Header: badges & metadata */}
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div className="flex flex-wrap items-center gap-2">
            <ChangeTypeBadge type={card.change_type} />
            {card.materiality === 'high' && (
              <Badge variant="outline" className="border-destructive px-1.5 py-0 text-[10px] text-destructive">
                High Impact
              </Badge>
            )}
            {card.is_updated && (
              <Badge variant="outline" className="border-amber-200 bg-amber-500/10 text-[10px] text-amber-600">
                Updated Notice
              </Badge>
            )}
            <ApplicabilityTag applicability={card.applicability} targetTerm={targetTerm} />
          </div>

          <div className="flex items-center gap-1.5">
            <Button
              variant="ghost"
              size="sm"
              onClick={() => toggleSaved(card.public_id, card.is_saved)}
              disabled={isSaving}
              aria-label={card.is_saved ? 'Remove bookmark' : 'Bookmark amendment'}
              className="h-8 w-8 p-0 text-muted-foreground hover:text-foreground"
            >
              <Bookmark className={cn('h-4 w-4', card.is_saved && 'fill-primary text-primary')} />
            </Button>
          </div>
        </div>

        {/* Provision & Title */}
        <div className="mt-2.5">
          <div className="text-xs font-semibold tracking-wider text-muted-foreground uppercase">
            {card.law_label} {card.provision_label ? `· ${card.provision_label}` : ''}
          </div>
          <h3 className="mt-0.5 text-sm leading-snug font-semibold sm:text-base">
            <Link
              to="/app/amendments/$cardId"
              params={{ cardId: card.public_id }}
              className="hover:underline focus-visible:underline"
            >
              {card.title}
            </Link>
          </h3>
        </div>

        {/* Diff Pair (Before and After) */}
        {(card.summary_old || card.summary_new) && (
          <div className="mt-3">
            <DiffPair summaryOld={card.summary_old} summaryNew={card.summary_new} />
          </div>
        )}

        {/* Mapping context */}
        {primaryMapping && (
          <div className="mt-3 flex items-center gap-1 text-xs text-muted-foreground">
            <span className="font-medium text-foreground/80">{primaryMapping.subject_key}</span>
            {primaryMapping.chapter_key && (
              <>
                <span>/</span>
                <span>{primaryMapping.chapter_key}</span>
              </>
            )}
          </div>
        )}

        {/* Footer actions */}
        <div className="mt-4 flex flex-wrap items-center justify-between gap-3 border-t pt-3">
          <label className="flex cursor-pointer items-center gap-2 text-xs font-medium select-none">
            <Checkbox
              checked={card.is_reviewed}
              disabled={isReviewing}
              onCheckedChange={() => toggleReviewed(card.public_id, card.is_reviewed)}
            />
            <span className={card.is_reviewed ? 'text-muted-foreground line-through' : 'text-foreground'}>
              {card.is_reviewed ? 'Reviewed' : 'Mark as reviewed'}
            </span>
          </label>

          <div className="flex items-center gap-3">
            <ReportDialog publicId={card.public_id} cardTitle={card.title} />
            <OfficialPdfButton officialUrl={card.document.official_url} sourcePage={card.source_page} />
          </div>
        </div>
      </div>
    </Card>
  )
}
