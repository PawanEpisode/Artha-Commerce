import {
  Button,
  Sheet,
  SheetContent,
  SheetDescription,
  SheetFooter,
  SheetHeader,
  SheetTitle,
} from '@artha/design-system'
import { useEffect, useMemo, useRef, useState } from 'react'

import {
  AnnotationListAside,
  type AnnotationListProps,
  AnnotationListSheet,
} from '../components/annotations/AnnotationList'
import { MarksLimitNotice } from '../components/annotations/MarksLimitNotice'
import { annotationAnalytics } from '../lib/annotation-analytics'
import { applyFilters, NO_FILTERS, tagsOf, toRows } from '../lib/annotation-filters'
import { colorName } from '../lib/annotation-legend'
import { heaviestInkPages } from '../lib/annotation-limits'
import { MARKUP_COLORS } from '../lib/annotation-types'
import { KIND_LABEL } from '../lib/mark-label'
import { useUiScope } from './annotation-scope'

/**
 * The list of marks of this PDF: a side panel on wide screens (`panel=annotations` in the URL), a bottom sheet on phones.
 * It is also the accessible twin of the canvas, so every mark is reachable here with the keyboard.
 */
export function AnnotationListContainer() {
  const ui = useUiScope()
  const [filters, setFilters] = useState(NO_FILTERS)
  const [expanded, setExpanded] = useState<string | null>(null)
  const open = ui?.listOpen ?? false
  const marks = ui?.marks
  const legend = ui?.settings.legend

  const filtered = useMemo(() => (marks ? applyFilters(marks.marks, filters) : []), [marks, filters])
  const rows = useMemo(() => (legend ? toRows(filtered, legend) : []), [filtered, legend])
  const tags = useMemo(() => (marks ? tagsOf(marks.marks) : []), [marks])
  const heavy = useMemo(() => (marks ? heaviestInkPages(marks.all) : []), [marks])
  const filterCount = (filters.color ? 1 : 0) + (filters.kind ? 1 : 0) + (filters.tag ? 1 : 0) + (filters.today ? 1 : 0)
  const total = marks?.marks.length ?? 0

  // `chapter_notes_seen` for the reader: once each time the list opens, with how many filters and a count bucket.
  const seen = useRef(false)
  useEffect(() => {
    if (open && !seen.current && marks?.status === 'ready') {
      seen.current = true
      annotationAnalytics.chapterMarksSeen({ filters: filterCount, items: total })
    }
    if (!open) seen.current = false
  }, [open, marks?.status, filterCount, total])

  if (!ui || !marks || !legend) return null

  const focusAfterDelete = (id: string) => {
    const at = rows.findIndex((r) => r.id === id)
    const next = rows[at + 1]?.id ?? rows[at - 1]?.id
    requestAnimationFrame(() => {
      const target = next ? document.querySelector<HTMLElement>(`[data-id="${next}"] button`) : null
      ;(target ?? document.querySelector<HTMLElement>('[data-slot="annotation-list"]'))?.focus()
    })
  }

  const props: AnnotationListProps = {
    rows,
    total,
    status: marks.status,
    onRetry: () => void marks.syncNow(),
    filters,
    onFiltersChange: setFilters,
    colors: MARKUP_COLORS.map((key) => ({ key, name: colorName(key, legend) })),
    tags,
    selectedId: ui.search.ann ?? null,
    onOpen: (id) => {
      if (!ui.docked) ui.setListOpen(false)
      ui.goToMark(id)
    },
    onEdit: (id) => ui.openEdit(id),
    onDelete: (id) => {
      focusAfterDelete(id)
      marks.remove(id)
    },
    onExpand: setExpanded,
    notice: (
      <MarksLimitNotice
        notice={marks.notice}
        info={marks.info}
        heavyPages={heavy}
        onGoToPage={(p) => ui.apiRef.current?.goToPage(p)}
      />
    ),
    onClose: () => ui.setListOpen(false),
  }

  const full = expanded
    ? (rows.find((r) => r.id === expanded) ??
      toRows(
        marks.marks.filter((m) => m.id === expanded),
        legend,
      )[0])
    : null

  return (
    <>
      {ui.docked ? (
        open ? (
          <AnnotationListAside {...props} />
        ) : null
      ) : (
        <AnnotationListSheet {...props} open={open} onOpenChange={ui.setListOpen} />
      )}
      <Sheet open={full !== null && full !== undefined} onOpenChange={(next) => !next && setExpanded(null)}>
        <SheetContent side="bottom" className="max-h-[85dvh] overflow-y-auto sm:mx-auto sm:max-w-xl">
          <SheetHeader>
            <SheetTitle>{full ? full.heading : 'Mark'}</SheetTitle>
            <SheetDescription>
              {full ? [KIND_LABEL[full.kind], full.colorText, full.chapter].filter(Boolean).join(', ') : ''}
            </SheetDescription>
          </SheetHeader>
          <p className="text-sm break-words whitespace-pre-wrap">{full?.preview}</p>
          <SheetFooter>
            <Button
              variant="outline"
              className="min-h-11"
              onClick={() => {
                const id = expanded
                setExpanded(null)
                if (id) ui.openEdit(id)
              }}
            >
              Edit
            </Button>
          </SheetFooter>
        </SheetContent>
      </Sheet>
    </>
  )
}
