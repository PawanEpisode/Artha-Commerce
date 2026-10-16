import {
  ArrowRight,
  Button,
  Container,
  DataTable,
  EntityBadge,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@artha/design-system'
import { Link } from '@tanstack/react-router'
import type { ReactNode } from 'react'

import type { PublicCourse } from '../lib/load'

export function CourseDetail({ course, prompt }: { course: PublicCourse; prompt?: ReactNode }) {
  return (
    <Container className="py-6 sm:py-8">
      <header>
        <p className="text-[11px] font-medium tracking-wide text-muted-foreground uppercase">{course.body}</p>
        <h1 className="text-xl font-semibold tracking-tight">
          {course.fullName} ({course.name})
        </h1>
        <p className="mt-1 max-w-3xl text-sm text-muted-foreground">{course.description}</p>
      </header>
      <div className="mt-5 space-y-3">
        {prompt}
        <DataTable>
          <TableHeader>
            <TableRow className="hover:bg-transparent">
              <TableHead>Level</TableHead>
              <TableHead className="hidden md:table-cell">Papers include</TableHead>
              <TableHead className="text-right">Papers</TableHead>
              <TableHead>
                <span className="sr-only">Open</span>
              </TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {course.levels.map((l) => (
              <TableRow key={l.slug}>
                <TableCell className="h-12 py-2 text-sm font-medium">{l.name}</TableCell>
                <TableCell className="hidden max-w-md truncate text-muted-foreground md:table-cell">
                  {l.subjects.slice(0, 3).join(' · ')}
                  {l.subjects.length > 3 ? ' …' : ''}
                </TableCell>
                <TableCell className="text-right">
                  <EntityBadge kind="paper">{l.subjects.length}</EntityBadge>
                </TableCell>
                <TableCell className="text-right">
                  <Button variant="outline" size="sm" asChild>
                    <Link to="/courses/$course/$level" params={{ course: course.slug, level: l.slug }}>
                      Open<span className="sr-only"> {l.name} papers</span>
                      <ArrowRight aria-hidden />
                    </Link>
                  </Button>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </DataTable>
      </div>
    </Container>
  )
}
