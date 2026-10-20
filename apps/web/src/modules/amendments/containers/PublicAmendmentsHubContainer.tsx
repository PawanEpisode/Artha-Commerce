import { ArrowRight, Badge, Card, FileText, Page, ShieldCheck } from '@artha/design-system'
import { Link } from '@tanstack/react-router'

import type { PublicHub } from '../lib/types'

interface Props {
  hub: PublicHub | null
}

export function PublicAmendmentsHubContainer({ hub }: Props) {
  const documents = hub?.latest_documents ?? []
  const courses = hub?.courses ?? []

  return (
    <Page width="fluid" className="space-y-10 py-8">
      {/* Hero Section */}
      <div className="max-w-3xl space-y-3">
        <div className="inline-flex items-center gap-1.5 rounded-full bg-primary/10 px-3 py-1 text-xs font-semibold text-primary">
          <ShieldCheck className="h-4 w-4" />
          4-Eye Editorial Verification
        </div>
        <h1 className="text-3xl font-extrabold tracking-tight text-foreground sm:text-4xl">
          Statutory & Academic Amendments
        </h1>
        <p className="text-base text-muted-foreground sm:text-lg">
          Never study outdated law. Explore verified statutory amendments, notifications, and institute announcements
          mapped directly to your examination syllabus chapters.
        </p>
      </div>

      {/* Courses Grid */}
      {courses.length > 0 && (
        <section aria-labelledby="courses-heading" className="space-y-4">
          <h2 id="courses-heading" className="text-xl font-bold text-foreground">
            Browse by Professional Course
          </h2>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {courses.map((c) => (
              <Card key={c.code} className="flex flex-col justify-between p-5">
                <div>
                  <h3 className="text-lg font-semibold text-foreground">{c.name}</h3>
                  <div className="mt-2 flex flex-wrap gap-1.5">
                    {c.levels.map((lvl) => (
                      <Badge key={lvl.code} variant="outline" className="text-xs">
                        {lvl.name}
                      </Badge>
                    ))}
                  </div>
                </div>
                <div className="mt-5 border-t pt-3">
                  <Link
                    to="/courses"
                    className="inline-flex items-center gap-1 text-xs font-medium text-primary hover:underline"
                  >
                    View course syllabus & amendments
                    <ArrowRight className="h-3.5 w-3.5" />
                  </Link>
                </div>
              </Card>
            ))}
          </div>
        </section>
      )}

      {/* Latest Official Documents */}
      <section aria-labelledby="docs-heading" className="space-y-4">
        <div className="flex items-center justify-between">
          <h2 id="docs-heading" className="text-xl font-bold text-foreground">
            Latest Authority Notifications & Guidelines
          </h2>
        </div>

        {documents.length === 0 ? (
          <Card className="p-8 text-center text-sm text-muted-foreground">No amendment documents published yet.</Card>
        ) : (
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            {documents.map((doc) => (
              <Card key={doc.slug} className="flex flex-col justify-between p-5">
                <div>
                  <div className="flex items-center justify-between text-xs text-muted-foreground">
                    <span className="font-semibold tracking-wider text-primary uppercase">
                      {doc.course} · {doc.level}
                    </span>
                    {doc.issued_on && <span>Issued: {new Date(doc.issued_on).toLocaleDateString()}</span>}
                  </div>

                  <h3 className="mt-2 text-base leading-snug font-semibold text-foreground">
                    <Link to="/amendments/documents/$slug" params={{ slug: doc.slug }} className="hover:underline">
                      {doc.title}
                    </Link>
                  </h3>

                  <div className="mt-2 flex flex-wrap gap-1.5">
                    <Badge variant="outline" className="text-[10px]">
                      {doc.issuer_label}
                    </Badge>
                    <Badge variant="outline" className="text-[10px]">
                      Rev #{doc.revision_no}
                    </Badge>
                    {doc.terms.map((t) => (
                      <Badge
                        key={t.term_code}
                        variant={t.applicability === 'applies' ? 'accent' : 'outline'}
                        className="text-[10px]"
                      >
                        {t.term_code}
                      </Badge>
                    ))}
                  </div>
                </div>

                <div className="mt-5 flex items-center justify-between border-t pt-3">
                  <Link
                    to="/amendments/documents/$slug"
                    params={{ slug: doc.slug }}
                    className="inline-flex items-center gap-1 text-xs font-medium text-foreground hover:text-primary"
                  >
                    View amendment breakdown
                    <ArrowRight className="h-3.5 w-3.5" />
                  </Link>

                  <a
                    href={doc.official_url}
                    target="_blank"
                    rel="noreferrer noopener"
                    className="inline-flex items-center gap-1 text-xs text-muted-foreground hover:underline"
                  >
                    <FileText className="h-3 w-3" />
                    Official PDF
                  </a>
                </div>
              </Card>
            ))}
          </div>
        )}
      </section>

      {/* Verification Notice Banner */}
      <div className="flex flex-col items-start justify-between gap-4 rounded-lg border border-border bg-card p-6 sm:flex-row sm:items-center">
        <div className="space-y-1">
          <h3 className="font-semibold text-foreground">Track amendments in your student workspace</h3>
          <p className="max-w-xl text-xs text-muted-foreground">
            Get personalized attempt-wise applicability filtering, mark individual changes as reviewed, bookmark
            high-impact provisions, and sync offline.
          </p>
        </div>
        <Link
          to="/signup"
          className="inline-flex shrink-0 items-center justify-center rounded-md bg-primary px-4 py-2 text-xs font-semibold text-primary-foreground hover:bg-primary/90"
        >
          Create Free Student Account
        </Link>
      </div>
    </Page>
  )
}
