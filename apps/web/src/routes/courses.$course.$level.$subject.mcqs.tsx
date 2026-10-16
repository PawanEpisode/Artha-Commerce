import { ArrowLeft, Badge, ButtonLink, Card, Container } from '@artha/design-system'
import { createFileRoute, Link, notFound } from '@tanstack/react-router'

import { findLevel, loadCourse } from '~/modules/courses'
import { publicPage } from '~/modules/layout'
import { listMcqSets, SetsTable } from '~/modules/mcqbank'
import { buildHead } from '~/modules/seo'
import { fetchSubject } from '~/modules/syllabus'

export const Route = createFileRoute('/courses/$course/$level/$subject/mcqs')({
  staticData: publicPage,
  loader: async ({ params }) => {
    const course = await loadCourse(params.course)
    const level = course && findLevel(course, params.level)
    if (!course || !level) throw notFound()
    const subject = await fetchSubject(params.course, params.level, params.subject)
    if (!subject) throw notFound()

    const sets = await listMcqSets({ subject: subject.key }).catch(() => [])

    return { course, level, subject, sets }
  },
  head: ({ loaderData }) =>
    buildHead({
      title: loaderData
        ? `${loaderData.subject.name} MCQs: ${loaderData.course.name} ${loaderData.level.name}`
        : 'Subject MCQs',
      description: loaderData
        ? `Practise multiple choice questions and ICMAI booklets for ${loaderData.subject.name} (${loaderData.course.name} ${loaderData.level.name}).`
        : 'Multiple choice practice and official institute booklets.',
      path: loaderData
        ? `/courses/${loaderData.course.slug}/${loaderData.level.slug}/${loaderData.subject.key}/mcqs`
        : '/courses',
    }),
  component: function SubjectMcqsRoute() {
    const { course, level, subject, sets } = Route.useLoaderData()

    return (
      <Container className="space-y-6 py-8">
        <div className="space-y-4">
          <ButtonLink
            asChild
            variant="ghost"
            size="sm"
            className="-ml-2 gap-1.5 text-xs text-muted-foreground hover:text-foreground"
          >
            <Link
              to="/courses/$course/$level/$subject"
              params={{
                course: course.slug,
                level: level.slug,
                subject: subject.key,
              }}
            >
              <ArrowLeft className="h-3.5 w-3.5" />
              Back to {subject.name}
            </Link>
          </ButtonLink>

          <div className="flex flex-wrap items-center justify-between gap-4">
            <div>
              <div className="flex items-center gap-2">
                <h1 className="text-2xl font-semibold tracking-tight text-foreground sm:text-3xl">
                  {subject.name} MCQs
                </h1>
                <Badge variant="outline" className="font-mono text-xs uppercase">
                  {course.slug} {level.slug}
                </Badge>
              </div>
              <p className="mt-1 text-sm text-muted-foreground">
                Official ICMAI Directorate of Studies question banks and interactive practice sets for {subject.name}.
              </p>
            </div>

            <ButtonLink asChild>
              <Link to="/app/mcq/subjects/$subject" params={{ subject: subject.key }}>
                Open Interactive Bank
              </Link>
            </ButtonLink>
          </div>
        </div>

        {sets.length > 0 ? (
          <SetsTable sets={sets} />
        ) : (
          <Card className="p-8 text-center text-muted-foreground">
            No public MCQ booklets currently published for this subject. Check back soon or open the interactive bank in
            the workspace.
          </Card>
        )}
      </Container>
    )
  },
})
