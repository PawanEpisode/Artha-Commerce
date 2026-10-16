import {
  Alert,
  Button,
  ButtonLink,
  Card,
  CircleAlert,
  CircleCheck,
  DataTable,
  Label,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
  Textarea,
  Upload,
} from '@artha/design-system'
import { Link } from '@tanstack/react-router'
import { type ReactNode, useRef } from 'react'

import {
  doneDetail,
  doneHeading,
  IMPORT_EXAMPLE_COLUMNS,
  IMPORT_EXAMPLE_PLAIN,
  IMPORT_ROW_LIMIT,
  previewSentence,
  rowResult,
} from '../lib/importFlow'
import type { ImportResult } from '../lib/schemas'

export type ImportPhase = 'idle' | 'checking' | 'importing'

interface ImportPanelProps {
  text: string
  onText: (text: string) => void
  onFile: (file: File) => void
  /** The chapter chooser for rows that name none (the container passes it in, so this stays props only). */
  chapterField: ReactNode
  phase: ImportPhase
  offline: boolean
  /** The last judged rows: a preview, or the result of the real import. */
  result: ImportResult | null
  canImport: boolean
  error: string | null
  onCheck: () => void
  onImport: () => void
  onReset: () => void
}

function ResultTable({ result }: { result: ImportResult }) {
  return (
    <div
      role="region"
      aria-label="Checked rows"
      // eslint-disable-next-line jsx-a11y/no-noninteractive-tabindex -- a scrollable region must be reachable by keyboard
      tabIndex={0}
      className="overflow-x-auto rounded-lg focus-visible:ring-2 focus-visible:ring-ring/50 focus-visible:outline-none"
    >
      <DataTable className="min-w-[34rem]" containerClassName="overflow-visible">
        <caption className="sr-only">
          {result.dry_run ? 'Each row and whether it can be imported' : 'Each row and what happened to it'}
        </caption>
        <TableHeader>
          <TableRow>
            <TableHead scope="col">Line</TableHead>
            <TableHead scope="col">Kind</TableHead>
            <TableHead scope="col">Front</TableHead>
            <TableHead scope="col">Back</TableHead>
            <TableHead scope="col">Result</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {result.rows.map((row) => {
            const outcome = rowResult(row)
            return (
              <TableRow key={row.line} className="align-top">
                <TableCell className="h-auto py-2 tabular-nums">{row.line}</TableCell>
                <TableCell className="h-auto py-2">{row.kind ?? ''}</TableCell>
                <TableCell className="h-auto max-w-[14rem] py-2 break-words">{row.front}</TableCell>
                <TableCell className="h-auto max-w-[14rem] py-2 break-words">{row.back}</TableCell>
                <TableCell className="h-auto py-2">
                  {outcome.lines.map((line) => (
                    <span
                      key={line}
                      className={
                        outcome.tone === 'error' ? 'flex items-start gap-1.5 text-error-fg' : 'flex items-start gap-1.5'
                      }
                    >
                      {outcome.tone === 'error' ? (
                        <CircleAlert aria-hidden className="mt-0.5 size-3.5 shrink-0" />
                      ) : (
                        <CircleCheck aria-hidden className="mt-0.5 size-3.5 shrink-0" />
                      )}
                      <span>{line}</span>
                    </span>
                  ))}
                </TableCell>
              </TableRow>
            )
          })}
        </TableBody>
      </DataTable>
    </div>
  )
}

/**
 * The import panel of the card creator: paste rows or pick a CSV file, check them, see every row with its problem, then make the
 * cards. Props only. The state, the calls and the 44 px buttons' behaviour live in `ImportContainer`.
 */
export function ImportPanel(props: ImportPanelProps) {
  const { text, result, phase, offline, error } = props
  const fileInput = useRef<HTMLInputElement>(null)
  const busy = phase !== 'idle'
  const done = result !== null && !result.dry_run

  if (done && result) {
    return (
      <section
        aria-labelledby="import-done-h"
        className="space-y-3 rounded-lg border border-border bg-card p-4"
        role="status"
      >
        <h2 id="import-done-h" className="text-base font-semibold">
          {doneHeading(result)}
        </h2>
        <p className="text-[13px] text-muted-foreground">{doneDetail(result)}</p>
        {result.invalid > 0 ? <ResultTable result={result} /> : null}
        <div className="flex flex-wrap gap-2">
          <Button onClick={props.onReset}>Import more</Button>
          <ButtonLink variant="outline" asChild>
            <Link to="/app/recall/cards" search={{}}>
              See your cards
            </Link>
          </ButtonLink>
        </div>
      </section>
    )
  }

  return (
    <section aria-labelledby="import-h" className="space-y-3">
      <header className="space-y-0.5">
        <h2 id="import-h" className="text-sm font-semibold">
          Import many cards
        </h2>
        <p className="text-[13px] text-muted-foreground">
          Paste one card per line, or choose a CSV file. You see every row before anything is made. Up to{' '}
          {IMPORT_ROW_LIMIT} rows at a time.
        </p>
      </header>

      {offline ? (
        <Alert variant="info">You are offline. Importing needs a connection, so it waits until you are back.</Alert>
      ) : null}

      <div className="grid gap-4 lg:grid-cols-[minmax(0,26rem)_minmax(0,1fr)] lg:items-start">
        <Card className="min-w-0 space-y-3 p-4">
          <div className="space-y-1.5">
            <Label htmlFor="import-text">Your rows</Label>
            <Textarea
              id="import-text"
              value={text}
              rows={8}
              className="min-h-40 font-mono"
              aria-describedby="import-help"
              spellCheck={false}
              onChange={(e) => props.onText(e.target.value)}
            />
            <div id="import-help" className="space-y-1 text-xs text-muted-foreground">
              <p>
                One card per line: <code className="rounded bg-muted px-1.5 py-0.5">{IMPORT_EXAMPLE_PLAIN}</code>
              </p>
              <p>
                Or columns, with this first line:{' '}
                <code className="rounded bg-muted px-1.5 py-0.5 break-all">
                  {IMPORT_EXAMPLE_COLUMNS.split('\n')[0]}
                </code>
                . The chapter column is optional.
              </p>
            </div>
            <input
              ref={fileInput}
              type="file"
              accept=".csv,.tsv,.txt,text/csv,text/plain"
              className="sr-only"
              tabIndex={-1}
              aria-hidden
              onChange={(e) => {
                const file = e.target.files?.[0]
                if (file) props.onFile(file)
                e.target.value = ''
              }}
            />
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={() => fileInput.current?.click()}
              disabled={busy}
            >
              <Upload aria-hidden className="size-3.5" /> Choose a CSV file
            </Button>
          </div>

          <div className="space-y-1.5">{props.chapterField}</div>

          {error ? (
            <Alert variant="error" role="alert">
              {error}
            </Alert>
          ) : null}

          <Button
            type="button"
            variant={result ? 'outline' : 'default'}
            loading={phase === 'checking'}
            disabled={busy || offline || text.trim().length === 0}
            onClick={props.onCheck}
          >
            {phase === 'checking' ? 'Checking…' : 'Check rows'}
          </Button>
        </Card>

        <div aria-live="polite" className="min-w-0 space-y-3">
          {result && result.dry_run ? (
            <Card className="space-y-3 p-4">
              <p className="font-medium">{previewSentence(result)}</p>
              {result.rows.length > 0 ? <ResultTable result={result} /> : null}
              {!result.quota.fits && result.valid > 0 ? (
                <Alert variant="error">
                  These rows need {result.quota.needed} card slots and your plan has room for {result.quota.room} more.
                  Remove some rows, or free up space, then check again.
                </Alert>
              ) : null}
              <div className="flex flex-wrap gap-2">
                <Button
                  type="button"
                  loading={phase === 'importing'}
                  disabled={busy || offline || !props.canImport}
                  onClick={props.onImport}
                >
                  {phase === 'importing'
                    ? 'Importing…'
                    : `Import ${result.valid} ${result.valid === 1 ? 'row' : 'rows'}`}
                </Button>
                <Button type="button" variant="ghost" disabled={busy} onClick={props.onReset}>
                  Start over
                </Button>
              </div>
            </Card>
          ) : null}
          {!result && text.trim().length === 0 && !error ? (
            <p className="text-[13px] text-muted-foreground">Nothing to check yet. Paste your rows to begin.</p>
          ) : null}
        </div>
      </div>
    </section>
  )
}
