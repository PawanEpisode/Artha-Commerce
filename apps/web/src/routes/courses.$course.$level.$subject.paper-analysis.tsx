import { ArrowLeft, Card, Container } from '@artha/design-system'
import { createFileRoute, Link, notFound } from '@tanstack/react-router'

import { publicApi } from '~/lib/api'
import { findLevel, loadCourse } from '~/modules/courses'
import { publicPage } from '~/modules/layout'
import { DisclaimerNote } from '~/modules/paperanalysis'
import { buildHead } from '~/modules/seo'
import { fetchSubject } from '~/modules/syllabus'

interface PublicChapterAnalysis {
  chapter_id: string
  name: string
  asked_n: number
  papers_considered: number
  avg_effective: number
  max_effective: number | null
  trend: number | null
}

interface PublicPatterns {
  papers_considered?: number
  avg_total_marks?: number
  avg_attemptable_marks?: number
  avg_objective_pct?: number
  avg_practical_pct?: number
}

interface PublicPaperAnalysisData {
  subject_key: string
  subject_name: string
  chapters: PublicChapterAnalysis[]
  patterns: PublicPatterns | null
}

export const Route = createFileRoute('/courses/$course/$level/$subject/paper-analysis')({
  staticData: publicPage,
  loader: async ({ params }) => {
    const course = await loadCourse(params.course)
    const level = course && findLevel(course, params.level)
    if (!course || !level) throw notFound()
    const subject = await fetchSubject(params.course, params.level, params.subject)
    if (!subject) throw notFound()

    const analysis = await publicApi<PublicPaperAnalysisData>(
      `/paperanalysis/public/${params.course}/${params.level}/${params.subject}/`,
    ).catch(() => null)

    return { course, level, subject, analysis }
  },
  head: ({ loaderData }) =>
    buildHead({
      title: loaderData
        ? `${loaderData.subject.name} Past Paper Analysis & Chapter Weightage: ${loaderData.course.name} ${loaderData.level.name}`
        : 'Subject Past Paper Analysis',
      description: loaderData
        ? `Historical exam questions and chapter frequency trends for ${loaderData.subject.name} (${loaderData.course.name} ${loaderData.level.name}).`
        : 'Past exam chapter analysis and weightages.',
      path: loaderData
        ? `/courses/${loaderData.course.slug}/${loaderData.level.slug}/${loaderData.subject.key}/paper-analysis`
        : '/courses',
    }),
  component: function PublicPaperAnalysisRoute() {
    const { course, level, subject, analysis } = Route.useLoaderData()
    const chapters = analysis?.chapters || []
    const patterns = analysis?.patterns

    return (
      <Container className="max-w-5xl space-y-6 py-8">
        <div className="space-y-4">
          <Link
            to="/courses/$course/$level/$subject"
            params={{
              course: course.slug,
              level: level.slug,
              subject: subject.key,
            }}
            className="inline-flex items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground"
          >
            <ArrowLeft className="h-3.5 w-3.5" />
            Back to {subject.name}
          </Link>

          <div>
            <h1 className="text-2xl font-bold tracking-tight text-foreground">
              {subject.name}: Past Paper Analysis & Trends
            </h1>
            <p className="mt-1 text-sm text-muted-foreground">
              Historical exam weightage and question frequencies across official exam sittings.
            </p>
          </div>
        </div>

        <DisclaimerNote />

        {/* Paper Patterns Overview */}
        {patterns && (
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
            <Card className="p-4">
              <span className="block text-xs text-muted-foreground">Analysed Past Papers</span>
              <span className="mt-1 block font-mono text-xl font-bold text-foreground">
                {patterns.papers_considered} sittings
              </span>
            </Card>
            <Card className="p-4">
              <span className="block text-xs text-muted-foreground">Average Paper Marks</span>
              <span className="mt-1 block font-mono text-xl font-bold text-foreground">
                {patterns.avg_total_marks?.toFixed(1)}m
              </span>
            </Card>
            <Card className="p-4">
              <span className="block text-xs text-muted-foreground">Attemptable Marks</span>
              <span className="mt-1 block font-mono text-xl font-bold text-primary">
                {patterns.avg_attemptable_marks?.toFixed(1)}m
              </span>
            </Card>
          </div>
        )}

        {/* Chapter Table */}
        <div className="overflow-hidden rounded-xl border border-border bg-card shadow-xs">
          <div className="border-b border-border bg-muted/40 p-4 text-xs font-semibold text-foreground">
            Chapter Historical Frequency Table
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="border-b border-border bg-muted/20 font-mono text-[10px] tracking-wider text-muted-foreground uppercase">
                <tr>
                  <th className="p-3">Chapter</th>
                  <th className="p-3">Times Asked</th>
                  <th className="p-3">Avg Effective Marks</th>
                  <th className="p-3">Max Marks in Sitting</th>
                  <th className="p-3">Trend</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border/60">
                {chapters.length === 0 ? (
                  <tr>
                    <td colSpan={5} className="p-6 text-center text-muted-foreground">
                      No chapter analysis published for this subject yet.
                    </td>
                  </tr>
                ) : (
                  chapters.map((ch: PublicChapterAnalysis) => (
                    <tr key={ch.chapter_id} className="transition-colors hover:bg-muted/30">
                      <td className="p-3 font-medium text-foreground">{ch.name}</td>
                      <td className="p-3 font-mono">
                        {ch.asked_n} / {ch.papers_considered}
                      </td>
                      <td className="p-3 font-mono font-semibold text-foreground">{ch.avg_effective?.toFixed(1)}m</td>
                      <td className="p-3 font-mono text-muted-foreground">
                        {ch.max_effective !== null ? `${ch.max_effective.toFixed(1)}m` : '—'}
                      </td>
                      <td className="p-3 font-mono">
                        {ch.trend !== null ? (
                          <span
                            className={
                              ch.trend > 0
                                ? 'font-semibold text-emerald-600 dark:text-emerald-400'
                                : ch.trend < 0
                                  ? 'text-amber-600 dark:text-amber-400'
                                  : 'text-muted-foreground'
                            }
                          >
                            {ch.trend > 0 ? `+${ch.trend.toFixed(2)}` : ch.trend.toFixed(2)}
                          </span>
                        ) : (
                          '—'
                        )}
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>
      </Container>
    )
  },
})
