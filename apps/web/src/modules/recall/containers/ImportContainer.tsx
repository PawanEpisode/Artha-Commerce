import { toast } from '@artha/design-system'
import { useRef, useState } from 'react'

import { ChapterPicker, type PickedChapter } from '../components/ChapterPicker'
import { ImportPanel, type ImportPhase } from '../components/ImportPanel'
import { NewCardModes } from '../components/NewCardModes'
import { useImportCards } from '../hooks/useImportCards'
import { useOnlineStatus } from '../hooks/useRecallBasics'
import type { NewCardSearch } from '../lib/cardSearch'
import { canImport, IMPORT_FILE_MAX_BYTES, importFailure } from '../lib/importFlow'
import type { ImportResult } from '../lib/schemas'
import { SuggestLink } from './SuggestLink'

const newId = (): string => crypto.randomUUID()

/**
 * Import state and calls. One batch id per pasted text: a retry after a dropped answer (or a second tap) can never make the
 * cards twice, and editing the text starts a new batch. Editing after a check also drops the check, so the button never
 * imports rows other than the ones she saw.
 */
export function ImportContainer({ search }: { search: NewCardSearch }) {
  const online = useOnlineStatus()
  const run = useImportCards()
  const [text, setText] = useState('')
  const [chapter, setChapter] = useState<PickedChapter | null>(null)
  const [result, setResult] = useState<ImportResult | null>(null)
  const [checkedText, setCheckedText] = useState<string | null>(null)
  const [phase, setPhase] = useState<ImportPhase>('idle')
  const [error, setError] = useState<string | null>(null)
  const batch = useRef(newId())

  const chapterId = chapter?.id ?? search.chapter ?? null
  const changed = checkedText !== null && checkedText !== text

  const edit = (next: string) => {
    setText(next)
    setError(null)
    if (result?.dry_run) setResult(null) // the rows she saw are not these rows any more
    batch.current = newId()
  }

  const send = (dryRun: boolean) => {
    setError(null)
    setPhase(dryRun ? 'checking' : 'importing')
    run.mutate(
      { client_id: batch.current, dry_run: dryRun, text, chapter_id: chapterId },
      {
        onSuccess: (r) => {
          setResult(r)
          setCheckedText(dryRun ? text : null)
          if (!dryRun && r.created > 0) toast.success(`${r.created} ${r.created === 1 ? 'row' : 'rows'} imported.`)
        },
        onError: (e) => setError(importFailure(e)),
        onSettled: () => setPhase('idle'),
      },
    )
  }

  const reset = () => {
    setText('')
    setResult(null)
    setCheckedText(null)
    setError(null)
    batch.current = newId()
  }

  const readFile = async (file: File) => {
    if (file.size > IMPORT_FILE_MAX_BYTES) {
      setError('That file is too big. Split it into smaller files of 200 rows or fewer.')
      return
    }
    try {
      edit(await file.text())
    } catch {
      setError('We could not read that file. Try pasting its rows instead.')
    }
  }

  return (
    <>
      <NewCardModes search={search} extra={<SuggestLink chapter={search.chapter} />} />
      <ImportPanel
        text={text}
        onText={edit}
        onFile={(f) => void readFile(f)}
        chapterField={
          <>
            <ChapterPicker label="Chapter for rows that name none (optional)" onPick={setChapter} />
            {!chapter && search.chapter ? (
              <p className="text-sm text-muted-foreground">Rows without a chapter go in the chapter you came from.</p>
            ) : null}
          </>
        }
        phase={phase}
        offline={!online}
        result={result}
        canImport={canImport(result, changed)}
        error={error}
        onCheck={() => send(true)}
        onImport={() => send(false)}
        onReset={reset}
      />
    </>
  )
}
