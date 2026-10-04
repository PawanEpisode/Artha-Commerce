import { Link } from '@tanstack/react-router'
import { ArrowLeft } from 'lucide-react'
import { Button } from '~/components/ui/button'
import { Card } from '~/components/ui/card'
import { Container } from '~/design-system'
import type { Course, Level } from '~/modules/catalog'

export function LevelDetail({ course, level }: { course: Course; level: Level }) {
  return (
    <Container className="max-w-3xl py-16 sm:py-24">
      <Button variant="link" className="mb-6 px-0" asChild>
        <Link to="/courses/$course" params={{ course: course.slug }}>
          <ArrowLeft /> {course.name}
        </Link>
      </Button>
      <h1 className="text-4xl font-extrabold sm:text-5xl">
        {course.name} {level.name}
      </h1>
      <p className="mt-3 text-lg text-muted-foreground">
        {level.subjects.length} papers. Syllabus shown is indicative; confirm the current scheme with {course.body}.
      </p>
      <ol className="mt-10 space-y-3">
        {level.subjects.map((s, i) => (
          <Card key={s} className="flex items-center gap-4 p-4">
            <span className="grid size-9 place-items-center rounded-lg bg-secondary font-display font-bold text-primary">{i + 1}</span>
            <span className="font-medium">{s}</span>
          </Card>
        ))}
      </ol>
      <Button size="lg" className="mt-10" asChild>
        <Link to="/login">Plan my {level.name} prep</Link>
      </Button>
    </Container>
  )
}
