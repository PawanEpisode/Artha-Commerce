import {
  ArrowRight,
  Button,
  DataTable,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@artha/design-system'
import { Link } from '@tanstack/react-router'

import type { PublicCourse } from '../lib/load'

function paperCount(course: PublicCourse): number {
  return course.levels.reduce((sum, level) => sum + level.subjects.length, 0)
}

/** Every course as one row: name, levels, paper count, and the way in. */
export function CoursesTable({ courses }: { courses: PublicCourse[] }) {
  return (
    <DataTable>
      <TableHeader>
        <TableRow className="hover:bg-transparent">
          <TableHead>Course</TableHead>
          <TableHead className="hidden md:table-cell">Levels</TableHead>
          <TableHead className="text-right">Papers</TableHead>
          <TableHead>
            <span className="sr-only">Open</span>
          </TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {courses.map((course) => {
          const papers = paperCount(course)
          return (
            <TableRow key={course.slug}>
              <TableCell className="h-14 py-2">
                <div className="flex min-w-0 items-center gap-3">
                  <span className="w-10 shrink-0 text-base font-semibold text-primary">{course.name}</span>
                  <div className="min-w-0">
                    <p className="truncate text-sm font-medium">{course.fullName}</p>
                    <p className="truncate text-[13px] text-muted-foreground">{course.tagline}</p>
                  </div>
                </div>
              </TableCell>
              <TableCell className="hidden text-muted-foreground md:table-cell">
                {course.levels.map((level) => level.name).join(' · ')}
              </TableCell>
              <TableCell className="text-right text-muted-foreground tabular-nums">{papers || '–'}</TableCell>
              <TableCell className="text-right">
                <Button variant="outline" size="sm" asChild>
                  <Link to="/courses/$course" params={{ course: course.slug }}>
                    Browse<span className="sr-only"> {course.name} papers</span>
                    <ArrowRight aria-hidden />
                  </Link>
                </Button>
              </TableCell>
            </TableRow>
          )
        })}
      </TableBody>
    </DataTable>
  )
}
