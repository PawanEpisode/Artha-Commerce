import { Alert, Button, Card, Label, LoaderCircle, Select } from '@artha/design-system'
import { type ReactNode, useState } from 'react'

import type { SwitchCarried, SwitchSummary } from '../lib/types'

interface Scheme {
  id: string
  code: string
  name: string
}

interface Props {
  current: Scheme
  options: Scheme[]
  pending: boolean
  error?: string
  summary?: SwitchSummary
  onSwitch: (to: Scheme) => void
}

function ChapterLine({ name, subject, note }: { name: string; subject: string; note?: string }) {
  return (
    <li className="text-sm">
      <span className="font-medium">{name}</span>
      <span className="text-muted-foreground">
        {' '}
        in {subject}
        {note ? `, ${note}` : ''}
      </span>
    </li>
  )
}

function Group({ title, count, children }: { title: string; count: number; children: ReactNode }) {
  if (count === 0) return null
  return (
    <details className="rounded-lg border p-3">
      <summary className="cursor-pointer text-sm font-semibold">
        {title} ({count})
      </summary>
      <ul className="mt-2 space-y-1.5">{children}</ul>
    </details>
  )
}

function relationNote(c: SwitchCarried): string | undefined {
  if (c.relation === 'merged') return `merged from ${c.from.map((f) => f.name).join(' and ')}`
  if (c.relation === 'split') return `split from ${c.from.map((f) => f.name).join(' and ')}`
  const old = c.from[0]
  return old && old.name !== c.name ? `was ${old.name}` : undefined
}

/** The chapters behind the counts, so a student can see exactly what moved (FR-28). */
export function SwitchLists({ summary }: { summary: SwitchSummary }) {
  return (
    <div className="space-y-2">
      <Group title="Carried over" count={summary.carried.length}>
        {summary.carried.map((c) => (
          <ChapterLine key={c.id} name={c.name} subject={c.subject.name} note={relationNote(c)} />
        ))}
      </Group>
      <Group title="New in this scheme" count={summary.new.length}>
        {summary.new.map((c) => (
          <ChapterLine key={c.id} name={c.name} subject={c.subject.name} />
        ))}
      </Group>
      <Group title="No longer in this scheme" count={summary.removed.length}>
        {summary.removed.map((c) => (
          <ChapterLine key={c.id} name={c.name} subject={c.subject.name} note="your progress is kept" />
        ))}
      </Group>
    </div>
  )
}

/** Move to another published scheme. Mapped chapters keep their progress (FR-28). */
export function SchemeSwitch({ current, options, pending, error, summary, onSwitch }: Props) {
  const others = options.filter((s) => s.id !== current.id)
  const [target, setTarget] = useState('')
  const chosen = others.find((s) => s.id === target)
  return (
    <Card className="space-y-4 p-6">
      <div>
        <h2 className="font-display text-xl font-bold">Syllabus scheme</h2>
        <p className="mt-1 text-sm text-muted-foreground">You are on {current.name}.</p>
      </div>
      {summary ? (
        <div className="space-y-3">
          <Alert variant="success">
            Switched. {summary.carried_chapters} chapters carried your progress, {summary.new_chapters} are new
            {summary.removed_chapters
              ? `, and ${summary.removed_chapters} no longer exist in the new scheme (your old progress is kept)`
              : ''}
            .
          </Alert>
          <SwitchLists summary={summary} />
        </div>
      ) : null}
      {others.length === 0 ? (
        <p className="text-sm text-muted-foreground">No other scheme is published for your level.</p>
      ) : (
        <div className="space-y-3">
          <div className="grid gap-2">
            <Label htmlFor="scheme-target">Switch to</Label>
            <Select id="scheme-target" value={target} onChange={(e) => setTarget(e.target.value)}>
              <option value="">Choose a scheme</option>
              {others.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.name}
                </option>
              ))}
            </Select>
          </div>
          {error ? <Alert variant="error">{error}</Alert> : null}
          <Button variant="outline" disabled={!chosen || pending} onClick={() => chosen && onSwitch(chosen)}>
            {pending ? <LoaderCircle className="animate-spin" aria-hidden /> : null}
            Switch scheme and carry over progress
          </Button>
        </div>
      )}
    </Card>
  )
}
