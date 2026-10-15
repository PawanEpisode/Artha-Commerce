import { Badge, ButtonLink, Card } from '@artha/design-system'
import { Link } from '@tanstack/react-router'
import * as React from 'react'

import type { PyqChoiceGroup, PyqPaperQuestion, SchemeRelation } from '../lib/types'

interface PaperQuestionTreeProps {
  questions: PyqPaperQuestion[]
  choiceGroups: PyqChoiceGroup[]
  className?: string
}

const schemeRelationBadge: Record<SchemeRelation, { label: string; className: string }> = {
  current: {
    label: '2022 Syllabus',
    className: 'bg-emerald-50 text-emerald-700 dark:bg-emerald-950/40 dark:text-emerald-300',
  },
  mapped: { label: 'Mapped', className: 'bg-blue-50 text-blue-700 dark:bg-blue-950/40 dark:text-blue-300' },
  changed: {
    label: 'Changed in 2022',
    className: 'bg-amber-50 text-amber-700 dark:bg-amber-950/40 dark:text-amber-300',
  },
  unmapped: { label: 'Out of Syllabus', className: 'bg-zinc-100 text-zinc-600 dark:bg-zinc-800 dark:text-zinc-400' },
}

export function PaperQuestionTree({ questions, choiceGroups, className }: PaperQuestionTreeProps) {
  // Group questions by section / choice group
  const choiceGroupMap = React.useMemo(() => {
    return new Map(choiceGroups.map((cg) => [cg.id, cg]))
  }, [choiceGroups])

  // Group questions by section
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
    <div className={`space-y-6 ${className ?? ''}`}>
      {sections.map(([sectionName, sectionQuestions]) => (
        <section key={sectionName} className="space-y-3">
          <div className="flex items-center justify-between border-b border-border pb-2">
            <h3 className="text-sm font-bold tracking-wide text-foreground uppercase">{sectionName}</h3>
            <span className="text-xs font-medium text-muted-foreground">
              {sectionQuestions.length} {sectionQuestions.length === 1 ? 'item' : 'items'}
            </span>
          </div>

          <div className="space-y-2.5">
            {sectionQuestions.map((q) => {
              const cg = q.choice_group_id ? choiceGroupMap.get(q.choice_group_id) : null
              const rel = schemeRelationBadge[q.scheme_relation] || schemeRelationBadge.current

              return (
                <Card
                  key={q.id}
                  className="flex flex-col justify-between gap-3 p-3.5 transition-colors hover:bg-muted/20 sm:flex-row sm:items-center"
                >
                  <div className="min-w-0 flex-1 space-y-1.5">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="font-mono text-sm font-bold text-foreground">{q.number_label}</span>

                      <Badge variant="outline" className="text-xs">
                        {q.marks} {q.marks === '1.0' || q.marks === '1' ? 'mark' : 'marks'}
                      </Badge>

                      <span
                        className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${rel.className}`}
                      >
                        {rel.label}
                      </span>

                      {cg && (
                        <Badge variant="default" className="text-xs">
                          {cg.label}
                        </Badge>
                      )}
                    </div>

                    {q.descriptor && <p className="line-clamp-2 text-sm text-foreground">{q.descriptor}</p>}

                    <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
                      {q.chapter_key && (
                        <span className="font-medium">
                          Chapter: <span className="text-foreground">{q.chapter_key}</span>
                        </span>
                      )}
                      {q.answer_page_hint && (
                        <>
                          <span>•</span>
                          <span>Suggested Answer: {q.answer_page_hint}</span>
                        </>
                      )}
                    </div>
                  </div>

                  <div className="flex shrink-0 items-center gap-2 self-end sm:self-center">
                    {q.question_id && (
                      <ButtonLink asChild variant="outline" size="sm">
                        <Link to="/app/questions/$id" params={{ id: q.question_id }}>
                          Practise
                        </Link>
                      </ButtonLink>
                    )}
                  </div>
                </Card>
              )
            })}
          </div>
        </section>
      ))}
    </div>
  )
}
