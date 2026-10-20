import { ArrowLeft, ArrowUpRight, Badge, Card, FileText, Page, ShieldCheck } from '@artha/design-system'
import { Link } from '@tanstack/react-router'

import { ChangeTypeBadge } from '../components/ChangeTypeBadge'
import { DiffPair } from '../components/DiffPair'
import type { PublicDocument } from '../lib/types'

interface Props {
  document: PublicDocument
}

export function PublicDocumentContainer({ document: doc }: Props) {
  const cards = doc.cards ?? []

  return (
    <Page width="fluid" className="space-y-8 py-6">
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

      {/* Document Header Card */}
      <Card className="p-6">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-xs font-bold tracking-wider text-primary uppercase">
              {doc.course} · {doc.level}
            </span>
            <Badge variant="outline" className="text-xs">
              {doc.issuer_label}
            </Badge>
            <Badge variant="outline" className="text-xs">
              Revision #{doc.revision_no}
            </Badge>
          </div>

          <a
            href={doc.official_url}
            target="_blank"
            rel="noreferrer noopener"
            className="inline-flex items-center gap-1 rounded-md border px-3 py-1.5 text-xs font-medium text-foreground hover:bg-muted"
          >
            <FileText className="h-3.5 w-3.5" />
            Official Authority PDF
            <ArrowUpRight className="h-3 w-3" />
          </a>
        </div>

        <h1 className="mt-3 text-2xl font-bold tracking-tight text-foreground sm:text-3xl">{doc.title}</h1>

        {doc.issued_on && (
          <p className="mt-1 text-xs text-muted-foreground">Issued: {new Date(doc.issued_on).toLocaleDateString()}</p>
        )}

        {/* Attempt-wise applicability rules */}
        {doc.terms.length > 0 && (
          <div className="mt-5 border-t pt-4">
            <h2 className="mb-2 text-xs font-semibold tracking-wider text-muted-foreground uppercase">
              Examination Attempt Applicability
            </h2>
            <div className="flex flex-wrap gap-2">
              {doc.terms.map((t) => (
                <div
                  key={t.term_code}
                  className="flex items-center gap-2 rounded-md border bg-muted/30 px-3 py-1.5 text-xs"
                >
                  <span className="font-semibold text-foreground">{t.term_code}</span>
                  <Badge variant={t.applicability === 'applies' ? 'accent' : 'outline'} className="text-[10px]">
                    {t.applicability === 'applies' ? 'Applicable' : 'Excluded'}
                  </Badge>
                  {t.cutoff_date && (
                    <span className="text-[10px] text-muted-foreground">
                      Cut-off: {new Date(t.cutoff_date).toLocaleDateString()}
                    </span>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}
      </Card>

      {/* Change Cards Breakdown */}
      <section aria-labelledby="cards-breakdown-heading" className="space-y-4">
        <div className="flex items-center justify-between">
          <h2 id="cards-breakdown-heading" className="text-xl font-bold text-foreground">
            Extracted Change Cards ({cards.length})
          </h2>
          <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
            <ShieldCheck className="h-4 w-4 text-primary" />
            4-Eye Editorial Verification
          </div>
        </div>

        {cards.length === 0 ? (
          <Card className="p-8 text-center text-sm text-muted-foreground">
            No change cards available in this document version.
          </Card>
        ) : (
          <div className="space-y-4">
            {cards.map((card) => (
              <Card key={card.public_id} className="p-5">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div className="flex flex-wrap items-center gap-2">
                    <ChangeTypeBadge type={card.change_type} />
                    {card.materiality === 'high' && (
                      <Badge variant="outline" className="border-destructive text-[10px] text-destructive">
                        High Impact
                      </Badge>
                    )}
                    <span className="text-xs font-semibold text-muted-foreground uppercase">
                      {card.law_label} {card.provision_label ? `· ${card.provision_label}` : ''}
                    </span>
                  </div>

                  <span className="text-xs text-muted-foreground">Page {card.source_page}</span>
                </div>

                <h3 className="mt-2 text-base leading-snug font-semibold text-foreground">
                  <Link
                    to="/amendments/cards/$publicId"
                    params={{ publicId: card.public_id }}
                    className="hover:underline"
                  >
                    {card.title}
                  </Link>
                </h3>

                {(card.summary_old || card.summary_new) && (
                  <div className="mt-3">
                    <DiffPair summaryOld={card.summary_old} summaryNew={card.summary_new} />
                  </div>
                )}

                {card.chapters.length > 0 && (
                  <div className="mt-3 flex flex-wrap items-center gap-1.5 border-t pt-2.5 text-xs text-muted-foreground">
                    <span className="font-medium text-foreground">Mapped chapters:</span>
                    {card.chapters.map((ch, idx) => (
                      <span
                        key={`${ch.subject_key}-${ch.chapter_key}-${idx}`}
                        className="rounded bg-muted px-1.5 py-0.5"
                      >
                        {ch.subject_key} / {ch.chapter_name || ch.chapter_key}
                      </span>
                    ))}
                  </div>
                )}
              </Card>
            ))}
          </div>
        )}
      </section>
    </Page>
  )
}
