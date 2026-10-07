import { useCallback, useEffect, useRef, useState } from 'react'

import type { MarkRecord } from '../lib/annotation-types'

/** The mark before or after a place in reading order, wrapping at the ends. With none selected, from the current page. */
export function neighbourMark(
  marks: readonly Pick<MarkRecord, 'id' | 'page'>[],
  selectedId: string | undefined,
  currentPage: number,
  delta: 1 | -1,
): string | null {
  if (marks.length === 0) return null
  const at = selectedId ? marks.findIndex((m) => m.id === selectedId) : -1
  if (at >= 0) return marks[(at + delta + marks.length) % marks.length]?.id ?? null
  if (delta === 1) return (marks.find((m) => m.page >= currentPage) ?? marks[0])?.id ?? null
  for (let i = marks.length - 1; i >= 0; i--) if ((marks[i]?.page ?? 0) <= currentPage) return marks[i]?.id ?? null
  return marks[marks.length - 1]?.id ?? null
}

const PULSE_MS = 1_600

/** Goes to a mark: selects it in the URL (`ann`), scrolls to its page and plays the pulse once. */
export function useMarkNavigation(args: {
  marks: readonly MarkRecord[]
  selectedId: string | undefined
  currentPage: () => number
  goToPage: (page: number) => void
  select: (id: string) => void
}) {
  const { marks, selectedId, currentPage, goToPage, select } = args
  const [pulse, setPulse] = useState<{ id: string; nonce: number } | null>(null)
  const nonce = useRef(0)
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null)
  useEffect(() => () => void (timer.current && clearTimeout(timer.current)), [])

  const goToMark = useCallback(
    (id: string) => {
      const mark = marks.find((m) => m.id === id)
      if (!mark) return
      select(id)
      goToPage(mark.page)
      nonce.current += 1
      setPulse({ id, nonce: nonce.current })
      // The ring plays once (1.4 s); with reduced motion it is a still ring, so the app takes it away.
      if (timer.current) clearTimeout(timer.current)
      timer.current = setTimeout(() => setPulse(null), PULSE_MS)
    },
    [marks, select, goToPage],
  )

  const step = useCallback(
    (delta: 1 | -1) => {
      const id = neighbourMark(marks, selectedId, currentPage(), delta)
      if (id) goToMark(id)
      return id !== null
    },
    [marks, selectedId, currentPage, goToMark],
  )

  return { pulse, goToMark, step }
}
