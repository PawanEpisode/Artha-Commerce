import { ArrowRight, buttonVariants, Card, Reveal, Section } from '@artha/design-system'
import { Link } from '@tanstack/react-router'

import { courses } from '~/modules/catalog'

import { courseStories, paperCountForLevels } from '../data/story'

export function CourseCards() {
  return (
    <Section
      eyebrow="Courses"
      title="Pick the institute you sit"
      description="One workspace for ICAI, ICSI and ICMAI. Foundation through Final, chapter by chapter, with the same coverage, hours and notes."
    >
      <div className="grid gap-5 md:grid-cols-3">
        {courses.map((course, i) => {
          const story = courseStories[course.slug]
          const papers = paperCountForLevels(course.levels)
          return (
            <Reveal key={course.slug} delay={i * 0.08}>
              <Link
                to="/courses/$course"
                params={{ course: course.slug }}
                className="group block h-full rounded-xl outline-none focus-visible:ring-[3px] focus-visible:ring-ring/40"
              >
                <Card className="flex h-full flex-col p-7 transition-all group-hover:-translate-y-1 group-hover:shadow-lift">
                  <span className="font-display text-5xl font-extrabold text-primary">{course.name}</span>
                  <h3 className="mt-4 text-lg font-semibold">{course.fullName}</h3>
                  <p className="mt-2 text-sm leading-relaxed">{story.outcome}</p>
                  <p className="mt-3 text-sm text-muted-foreground">{story.insight}</p>
                  <p className="mt-5 text-xs font-medium text-muted-foreground">
                    {course.body} · {course.levels.length} levels · {papers} papers and modules
                  </p>
                  <p className="mt-1 text-xs text-muted-foreground">
                    {course.levels.map((level) => level.name).join(' · ')}
                  </p>
                  <span className="mt-5 block">
                    <span className={buttonVariants({ variant: 'outline', size: 'sm' })}>
                      Explore {course.name}
                      <ArrowRight
                        aria-hidden
                        className="transition-transform group-hover:translate-x-1 motion-reduce:transition-none"
                      />
                    </span>
                  </span>
                </Card>
              </Link>
            </Reveal>
          )
        })}
      </div>
    </Section>
  )
}
