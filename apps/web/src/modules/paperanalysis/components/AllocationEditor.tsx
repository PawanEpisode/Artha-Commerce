import { Button, Input } from '@artha/design-system'
import * as React from 'react'

import type { EditorialQuestion } from '../types'

export interface AllocationEditorProps {
  question: EditorialQuestion
  onSaveAllocations: (allocations: { chapter_id: string; marks: number }[]) => Promise<void>
  onConfirmQuestion: () => Promise<void>
  isSaving?: boolean
}

export function AllocationEditor({
  question,
  onSaveAllocations,
  onConfirmQuestion,
  isSaving = false,
}: AllocationEditorProps) {
  const targetMarks = parseFloat(question.marks)
  const [rows, setRows] = React.useState<{ chapter_id: string; chapter_name: string; marks: number }[]>(() =>
    question.allocations.map((a) => ({
      chapter_id: a.chapter_id,
      chapter_name: a.chapter_name || a.chapter_key,
      marks: parseFloat(a.marks),
    })),
  )

  const currentSum = rows.reduce((acc, r) => acc + (isNaN(r.marks) ? 0 : r.marks), 0)
  const isExactSum = Math.abs(currentSum - targetMarks) < 0.01

  const handleMarksChange = (idx: number, val: string) => {
    const num = parseFloat(val)
    setRows((prev) => {
      const next = [...prev]
      next[idx] = { ...next[idx], marks: isNaN(num) ? 0 : num }
      return next
    })
  }

  const handleSave = async () => {
    if (!isExactSum) return
    await onSaveAllocations(rows.map((r) => ({ chapter_id: r.chapter_id, marks: r.marks })))
  }

  return (
    <div className="space-y-4 rounded-xl border border-border bg-card p-4">
      <div className="flex items-center justify-between">
        <div>
          <span className="text-sm font-semibold text-foreground">
            {question.label} ({question.marks} marks)
          </span>
          <span className="ml-2 text-xs text-muted-foreground capitalize">
            {question.format} · {question.section_label}
          </span>
        </div>
        <div className="flex items-center gap-2">
          <span
            className={`rounded px-2 py-0.5 font-mono text-xs font-medium ${
              isExactSum
                ? 'bg-emerald-100 text-emerald-800 dark:bg-emerald-950/60 dark:text-emerald-300'
                : 'bg-destructive/15 text-destructive'
            }`}
          >
            Sum: {currentSum.toFixed(1)} / {targetMarks.toFixed(1)}m
          </span>
        </div>
      </div>

      <div className="space-y-2">
        {rows.map((row, idx) => (
          <div key={row.chapter_id || idx} className="flex items-center gap-3">
            <span className="flex-1 truncate text-xs font-medium text-foreground">{row.chapter_name}</span>
            <div className="w-24 shrink-0">
              <Input
                type="number"
                step="0.5"
                min="0.5"
                max={targetMarks}
                value={row.marks}
                onChange={(e) => handleMarksChange(idx, e.target.value)}
                className="h-8 font-mono text-xs"
              />
            </div>
          </div>
        ))}
      </div>

      <div className="flex items-center justify-end gap-2 border-t border-border pt-2">
        <Button size="sm" variant="outline" onClick={handleSave} disabled={!isExactSum || isSaving}>
          Save Allocations
        </Button>
        <Button
          size="sm"
          onClick={onConfirmQuestion}
          disabled={!isExactSum || question.alloc_state === 'confirmed' || isSaving}
        >
          {question.alloc_state === 'confirmed' ? 'Confirmed' : 'Confirm Question'}
        </Button>
      </div>
    </div>
  )
}
