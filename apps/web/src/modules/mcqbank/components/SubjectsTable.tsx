import {
  Badge,
  ChevronRight,
  DataTable,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@artha/design-system'
import { Link } from '@tanstack/react-router'

import type { SubjectCard } from '../lib/types'

/** Subjects of the MCQ bank as a table: paper, subject (link) and how many MCQs it holds. */
export function SubjectsTable({ subjects }: { subjects: SubjectCard[] }) {
  return (
    <DataTable>
      <TableHeader>
        <TableRow className="hover:bg-transparent">
          <TableHead className="w-28">Paper</TableHead>
          <TableHead>Subject</TableHead>
          <TableHead className="text-right">MCQs</TableHead>
          <TableHead className="w-8">
            <span className="sr-only">Open</span>
          </TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {subjects.map((sub) => (
          <TableRow key={sub.code}>
            <TableCell>
              <Badge variant="outline" className="uppercase">
                {sub.paper_number ? `Paper ${sub.paper_number}` : sub.code}
              </Badge>
            </TableCell>
            <TableCell className="py-2">
              <Link
                to="/app/mcq/subjects/$subject"
                params={{ subject: sub.code }}
                className="rounded-sm font-medium text-foreground outline-none hover:underline focus-visible:ring-2 focus-visible:ring-ring/50"
              >
                {sub.name}
              </Link>
            </TableCell>
            <TableCell className="text-right tabular-nums">{sub.total_mcqs}</TableCell>
            <TableCell className="text-muted-foreground">
              <ChevronRight aria-hidden className="size-4" />
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </DataTable>
  )
}
