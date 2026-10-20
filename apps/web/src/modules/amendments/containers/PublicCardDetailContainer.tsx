import { ArrowLeft, ArrowUpRight, Badge, Card, FileText, Page, ShieldCheck } from '@artha/design-system'
import { Link } from '@tanstack/react-router'

import { ChangeTypeBadge } from '../components/ChangeTypeBadge'
import { DiffPair } from '../components/DiffPair'
import { VerifyNotice } from '../components/VerifyNotice'
import type { PublicCard } from '../lib/types'

interface Props {
  card: PublicCard
}

export function PublicCardDetailContainer({ card }: Props) {
  return (
    <Page width="fluid" className="space-y-6 py-6">
      {/* Back Link */}
      <div>
        <Link
          to="/amendments"
          className="inline-flex items-center gap-1.5 text-xs font-medium text-muted-foreground hover:text-foreground"
        >
          <ArrowLeft className="h-3.5 w-3.5" />
          Back to Amendments Hub
        </Link>
      </div>

      {/* Main Card Header */}
      <Card className="p-6">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex flex-wrap items-center gap-2">
            <ChangeTypeBadge type={card.change_type} />
            {card.materiality === 'high' && (
              <Badge variant="outline" className="border-destructive text-xs text-destructive">
                High Impact
              </Badge>
            )}
            <Badge variant="outline" className="text-xs">
              {card.law_label}
            </Badge>
          </div>

          <a
            href={`${card.document.official_url}#page=${card.source_page}`}
            target="_blank"
            rel="noreferrer noopener"
            className="inline-flex items-center gap-1 rounded-md border px-3 py-1.5 text-xs font-medium text-foreground hover:bg-muted"
          >
            <FileText className="h-3.5 w-3.5" />
            Official PDF (p. {card.source_page})
            <ArrowUpRight className="h-3 w-3" />
          </a>
        </div>

        <div className="mt-4">
          <div className="text-xs font-semibold tracking-wider text-muted-foreground uppercase">
            {card.law_label} {card.provision_label ? `· ${card.provision_label}` : ''}
          </div>
          <h1 className="mt-1 text-2xl font-bold tracking-tight text-foreground sm:text-3xl">{card.title}</h1>
          {card.effective_text && <p className="mt-1 text-xs text-muted-foreground">{card.effective_text}</p>}
        </div>

        {/* Examination Terms Applicability */}
        {card.terms.length > 0 && (
          <div className="mt-6 border-t pt-4">
            <div className="mb-2 text-xs font-semibold text-muted-foreground uppercase">Attempt Applicability</div>
            <div className="flex flex-wrap gap-2">
              {card.terms.map((t) => (
                <div
                  key={t.term_code}
                  className="flex items-center gap-1.5 rounded border bg-muted/20 px-2.5 py-1 text-xs"
                >
                  <span className="font-medium text-foreground">{t.term_code}:</span>
                  <Badge variant={t.applicability === 'applies' ? 'accent' : 'outline'} className="text-[10px]">
                    {t.applicability === 'applies' ? 'Applies' : 'Excluded'}
                  </Badge>
                </div>
              ))}
            </div>
          </div>
        )}
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
      {card.chapters.length > 0 && (
        <section aria-labelledby="chapters-heading" className="space-y-3">
          <h2 id="chapters-heading" className="text-base font-semibold text-foreground">
            Affected Syllabus Chapters
          </h2>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            {card.chapters.map((m, idx) => (
              <Card key={`${m.subject_key}-${m.chapter_key}-${idx}`} className="p-4">
                <div className="flex items-start justify-between gap-2">
                  <div>
                    <div className="text-xs font-semibold text-primary uppercase">{m.subject_key}</div>
                    <div className="mt-1 text-sm font-medium text-foreground">{m.chapter_name || m.chapter_key}</div>
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
      )}

      {/* Official Authority Reference */}
      <section aria-labelledby="doc-ref-heading" className="space-y-3">
        <h2 id="doc-ref-heading" className="text-base font-semibold text-foreground">
          Authority Document Reference
        </h2>
        <Card className="flex flex-col gap-3 p-4 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex items-start gap-3">
            <FileText className="mt-0.5 h-5 w-5 shrink-0 text-primary" />
            <div>
              <div className="text-sm font-medium text-foreground">
                <Link
                  to="/amendments/documents/$slug"
                  params={{ slug: card.document.slug }}
                  className="hover:underline"
                >
                  {card.document.title}
                </Link>
              </div>
              <div className="mt-1 text-xs text-muted-foreground">Reference Page: {card.source_page}</div>
            </div>
          </div>
          <Link
            to="/amendments/documents/$slug"
            params={{ slug: card.document.slug }}
            className="inline-flex items-center gap-1 text-xs font-medium text-primary hover:underline"
          >
            View all cards in this document
          </Link>
        </Card>
      </section>

      {/* Verification Notice */}
      <VerifyNotice />

      {/* Student Workspace Call-to-action */}
      <div className="flex flex-col items-start justify-between gap-4 rounded-lg border border-primary/20 bg-primary/5 p-6 sm:flex-row sm:items-center">
        <div className="space-y-1">
          <div className="flex items-center gap-1.5 text-xs font-semibold text-primary">
            <ShieldCheck className="h-4 w-4" />
            Track this amendment for your exam
          </div>
          <p className="text-xs text-muted-foreground">
            Sign in to mark this card as reviewed, bookmark it for quick recall, and sync offline.
          </p>
        </div>
        <Link
          to="/signup"
          className="inline-flex shrink-0 items-center justify-center rounded-md bg-primary px-4 py-2 text-xs font-semibold text-primary-foreground hover:bg-primary/90"
        >
          Track in Workspace
        </Link>
      </div>
    </Page>
  )
}
