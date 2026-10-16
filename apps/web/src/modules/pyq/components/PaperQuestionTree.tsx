import { Badge, Button, DataTable, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@artha/design-system'
import { Link } from '@tanstack/react-router'
import * as React from 'react'

import { ResultLabel } from '~/modules/questionbank'

import { marksText } from '../lib/labels'
import type { PyqChoiceGroup, PyqPaperQuestion } from '../lib/types'
import { SchemeBadge } from './SchemeBadge'

interface PaperQuestionTreeProps {
  questions: PyqPaperQuestion[]
  choiceGroups: PyqChoiceGroup[]
  className?: string
}

/**
 * The paper's questions as one dense table, grouped by section. Sub-questions are indented by depth; rows that only
 * group children (no question of their own) read as headings. Practise opens the question in the bank.
 */
export function PaperQuestionTree({ questions, choiceGroups, className }: PaperQuestionTreeProps) {
  const choiceGroupMap = React.useMemo(() => new Map(choiceGroups.map((cg) => [cg.id, cg])), [choiceGroups])

  const sections = React.useMemo(() => {
    const map = new Map<string, PyqPaperQuestion[]>()
    for (const q of questions) {
      const section = q.section_label || 'Main Paper'
      const list = map.get(section) || []
      list.push(q)
      map.set(section, list)
    }
    return Array.from(map.entries())
  }, [questions])

  return (
    <DataTable className={className}>
      <TableHeader>
        <TableRow className="hover:bg-transparent">
          <TableHead className="w-16">No.</TableHead>
          <TableHead>Question</TableHead>
          <TableHead className="hidden text-right sm:table-cell">Marks</TableHead>
          <TableHead className="hidden sm:table-cell">Syllabus</TableHead>
          <TableHead className="hidden lg:table-cell">Chapter</TableHead>
          <TableHead className="hidden xl:table-cell">Suggested answer</TableHead>
          <TableHead className="hidden md:table-cell">Your result</TableHead>
          <TableHead className="text-right">
            <span className="sr-only">Action</span>
          </TableHead>
        </TableRow>
      </TableHeader>
      {sections.map(([sectionName, sectionQuestions]) => (
        <TableBody key={sectionName}>
          <TableRow className="bg-muted/30 hover:bg-muted/30">
            <TableCell colSpan={8} className="h-8 py-0">
              <span className="text-xs font-semibold tracking-wide text-foreground uppercase">{sectionName}</span>
              <span className="ml-2 text-xs text-muted-foreground">
                {sectionQuestions.length} {sectionQuestions.length === 1 ? 'item' : 'items'}
              </span>
            </TableCell>
          </TableRow>
          {sectionQuestions.map((q) => {
            const cg = q.choice_group_id ? choiceGroupMap.get(q.choice_group_id) : null
            return (
              <TableRow key={q.id}>
                <TableCell
                  className="font-mono text-xs font-semibold whitespace-nowrap"
                  style={q.depth > 0 ? { paddingLeft: `${0.875 + q.depth * 0.75}rem` } : undefined}
                >
                  {q.number_label}
                </TableCell>
                <TableCell className="min-w-48 py-2">
                  <p className={`line-clamp-2 ${q.is_leaf ? '' : 'font-medium'}`}>
                    {q.descriptor || <span className="text-muted-foreground">Question {q.number_label}</span>}
                  </p>
                  <p className="mt-0.5 flex flex-wrap items-center gap-x-1.5 text-xs text-muted-foreground sm:hidden">
                    <span className="tabular-nums">{marksText(q.marks)} marks</span>
                    <SchemeBadge relation={q.scheme_relation} short />
                  </p>
                  {cg && (
                    <Badge className="mt-1" variant="default">
                      {cg.label}
                    </Badge>
                  )}
                </TableCell>
                <TableCell className="hidden text-right tabular-nums sm:table-cell">{marksText(q.marks)}</TableCell>
                <TableCell className="hidden sm:table-cell">
                  <SchemeBadge relation={q.scheme_relation} />
                </TableCell>
                <TableCell className="hidden text-muted-foreground lg:table-cell">{q.chapter_key || '-'}</TableCell>
                <TableCell className="hidden text-muted-foreground xl:table-cell">
                  {q.answer_page_hint || '-'}
                </TableCell>
                <TableCell className="hidden text-xs whitespace-nowrap md:table-cell">
                  {q.user_state ? (
                    <ResultLabel result={q.user_state.last_result} />
                  ) : (
                    <span className="text-muted-foreground">-</span>
                  )}
                </TableCell>
                <TableCell className="text-right">
                  {q.question_id && (
                    <Button asChild variant="outline" size="sm">
                      <Link
                        to="/app/questions/$id"
                        params={{ id: q.question_id }}
                        aria-label={`Practise question ${q.number_label}`}
                      >
                        Practise
                      </Link>
                    </Button>
                  )}
                </TableCell>
              </TableRow>
            )
          })}
        </TableBody>
      ))}
    </DataTable>
  )
}
