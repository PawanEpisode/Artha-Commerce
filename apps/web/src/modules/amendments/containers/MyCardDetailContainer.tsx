import {
  Alert,
  ArrowLeft,
  ArrowUpRight,
  Badge,
  Bookmark,
  Button,
  Card,
  Checkbox,
  cn,
  FileText,
  Skeleton,
} from '@artha/design-system'
import { Link } from '@tanstack/react-router'

import { ApplicabilityTag } from '../components/ApplicabilityTag'
import { ChangeTypeBadge } from '../components/ChangeTypeBadge'
import { DiffPair } from '../components/DiffPair'
import { OfficialPdfButton } from '../components/OfficialPdfButton'
import { ReportDialog } from '../components/ReportDialog'
import { VerifyNotice } from '../components/VerifyNotice'
import { useCardActions } from '../hooks/useCardActions'
import { useMyCardDetail } from '../hooks/useMyCardDetail'
import { useMySummary } from '../hooks/useMySummary'
import { AmendmentsShell } from './AmendmentsShell'

interface Props {
  cardId: string
}

export function MyCardDetailContainer({ cardId }: Props) {
  const { data: summary } = useMySummary()
  const { data: card, isPending, isError, refetch } = useMyCardDetail(cardId)
  const { toggleReviewed, toggleSaved, isReviewing, isSaving } = useCardActions()

  return (
    <AmendmentsShell>
      <div className="space-y-6">
        {/* Navigation Breadcrumb / Back Link */}
        <div>
          <Link
            to="/app/amendments"
            className="inline-flex items-center gap-1.5 text-xs font-medium text-muted-foreground transition-colors hover:text-foreground"
          >
            <ArrowLeft className="h-3.5 w-3.5" />
            Back to My Amendments
          </Link>
        </div>

        {isPending ? (
          <div aria-busy="true" className="space-y-4">
            <span className="sr-only" role="status">
              Loading amendment detail…
            </span>
            <Skeleton className="h-8 w-64" />
            <Skeleton className="h-48 w-full" />
            <Skeleton className="h-36 w-full" />
          </div>
        ) : isError || !card ? (
          <Alert variant="error">
            <span className="flex flex-wrap items-center justify-between gap-3">
              <span>Could not load the requested amendment.</span>
              <Button size="sm" variant="outline" onClick={() => void refetch()}>
                Try again
              </Button>
            </span>
          </Alert>
        ) : (
          <div className="space-y-6">
            {/* Header Card */}
            <Card className="p-6">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div className="flex flex-wrap items-center gap-2">
                  <ChangeTypeBadge type={card.change_type} />
                  {card.materiality === 'high' && (
                    <Badge variant="outline" className="border-destructive text-xs text-destructive">
                      High Impact
                    </Badge>
                  )}
                  {card.is_updated && (
                    <Badge variant="outline" className="border-amber-300 bg-amber-500/10 text-xs text-amber-600">
                      Updated Notice
                    </Badge>
                  )}
                  <ApplicabilityTag applicability={card.applicability} targetTerm={summary?.target_term} />
                </div>

                {/* Bookmark action */}
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => toggleSaved(card.public_id, card.is_saved)}
                  disabled={isSaving}
                  className="gap-1.5 text-xs"
                >
                  <Bookmark className={cn('h-4 w-4', card.is_saved && 'fill-primary text-primary')} />
                  {card.is_saved ? 'Saved' : 'Save'}
                </Button>
              </div>

              {/* Title & Law */}
              <div className="mt-4">
                <div className="text-xs font-semibold tracking-wider text-muted-foreground uppercase">
                  {card.law_label} {card.provision_label ? `· ${card.provision_label}` : ''}
                </div>
                <h1 className="mt-1 text-xl font-bold tracking-tight text-foreground sm:text-2xl">{card.title}</h1>
                {card.effective_text && <p className="mt-1 text-xs text-muted-foreground">{card.effective_text}</p>}
              </div>

              {/* Quick Actions Footer */}
              <div className="mt-6 flex flex-wrap items-center justify-between gap-3 border-t pt-4">
                <label className="flex cursor-pointer items-center gap-2.5 text-sm font-medium select-none">
                  <Checkbox
                    checked={card.is_reviewed}
                    disabled={isReviewing}
                    onCheckedChange={() => toggleReviewed(card.public_id, card.is_reviewed)}
                  />
                  <span className={card.is_reviewed ? 'text-muted-foreground line-through' : 'text-foreground'}>
                    {card.is_reviewed ? 'Marked as reviewed' : 'Mark as reviewed'}
                  </span>
                </label>

                <div className="flex items-center gap-2.5">
                  <ReportDialog publicId={card.public_id} cardTitle={card.title} />
                  <OfficialPdfButton officialUrl={card.document.official_url} sourcePage={card.source_page} />
                </div>
              </div>
            </Card>

            {/* Before vs After Comparison */}
            {(card.summary_old || card.summary_new) && (
              <section aria-labelledby="diff-heading" className="space-y-2">
                <h2 id="diff-heading" className="text-base font-semibold text-foreground">
                  Statutory Comparison
                </h2>
                <DiffPair summaryOld={card.summary_old} summaryNew={card.summary_new} />
              </section>
            )}

            {/* Affected Chapters */}
            <section aria-labelledby="chapters-heading" className="space-y-3">
              <h2 id="chapters-heading" className="text-base font-semibold text-foreground">
                Affected Syllabus Chapters
              </h2>
              <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                {card.mappings.map((m, idx) => (
                  <Card key={`${m.subject_key}-${m.chapter_key}-${idx}`} className="p-4">
                    <div className="flex items-start justify-between gap-2">
                      <div>
                        <div className="text-xs font-semibold text-primary uppercase">{m.subject_key}</div>
                        <div className="mt-1 text-sm font-medium text-foreground">
                          {m.chapter_name || m.chapter_key}
                        </div>
                        <div className="mt-0.5 text-xs text-muted-foreground">Code: {m.chapter_key}</div>
                      </div>
                      {m.is_primary && (
                        <Badge variant="outline" className="text-[10px]">
                          Primary
                        </Badge>
                      )}
                    </div>
                  </Card>
                ))}
              </div>
            </section>

            {/* Source Document Reference */}
            <section aria-labelledby="source-heading" className="space-y-3">
              <h2 id="source-heading" className="text-base font-semibold text-foreground">
                Official Authority Document
              </h2>
              <Card className="p-4 sm:p-5">
                <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                  <div className="flex items-start gap-3">
                    <FileText className="mt-0.5 h-5 w-5 shrink-0 text-primary" />
                    <div>
                      <div className="text-sm font-medium text-foreground sm:text-base">{card.document.title}</div>
                      <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-muted-foreground">
                        {card.document.issuer_label && <span>Issuer: {card.document.issuer_label}</span>}
                        {card.document.issued_on && (
                          <span>Issued: {new Date(card.document.issued_on).toLocaleDateString()}</span>
                        )}
                        <span>Reference Page: {card.source_page}</span>
                      </div>
                    </div>
                  </div>

                  <a
                    href={`${card.document.official_url}#page=${card.source_page}`}
                    target="_blank"
                    rel="noreferrer noopener"
                    className="inline-flex items-center gap-1.5 rounded-md border px-3 py-1.5 text-xs font-medium text-foreground hover:bg-muted"
                  >
                    Open Official PDF
                    <ArrowUpRight className="h-3.5 w-3.5 text-muted-foreground" />
                  </a>
                </div>
              </Card>
            </section>

            {/* Quality & 4-Eye Verification Notice */}
            <VerifyNotice />
          </div>
        )}
      </div>
    </AmendmentsShell>
  )
}
