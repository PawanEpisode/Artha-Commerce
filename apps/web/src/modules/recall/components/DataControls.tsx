import { Alert, Button, Download, LoaderCircle, Trash2 } from '@artha/design-system'

import type { CsvKind } from '../lib/dataExport'

interface Props {
  busy: 'json' | CsvKind | null
  error: string | null
  onExportJson: () => void
  onExportCsv: (kind: CsvKind) => void
  onErase: () => void
}

/** Export and erase (FR-F15-75). Always reachable, even while the feature itself is switched off for the student. */
export function DataControls({ busy, error, onExportJson, onExportCsv, onErase }: Props) {
  return (
    <section
      aria-labelledby="recall-data-heading"
      className="space-y-4 rounded-2xl border border-border bg-card p-4 sm:p-6"
    >
      <div className="space-y-1">
        <h2 id="recall-data-heading" className="font-display text-lg font-bold">
          Your revision data
        </h2>
        <p className="text-sm text-muted-foreground">
          Download everything we hold for your revision cards, or erase it. Cards you copied from our decks are listed
          without their text.
        </p>
      </div>
      <div className="flex flex-col gap-3 sm:flex-row sm:flex-wrap">
        <Button variant="outline" disabled={busy !== null} aria-busy={busy === 'json'} onClick={onExportJson}>
          {busy === 'json' ? <LoaderCircle aria-hidden className="animate-spin" /> : <Download aria-hidden />}
          Download everything (JSON)
        </Button>
        <Button
          variant="outline"
          disabled={busy !== null}
          aria-busy={busy === 'cards'}
          onClick={() => onExportCsv('cards')}
        >
          {busy === 'cards' ? <LoaderCircle aria-hidden className="animate-spin" /> : <Download aria-hidden />}
          Cards (CSV)
        </Button>
        <Button
          variant="outline"
          disabled={busy !== null}
          aria-busy={busy === 'reviews'}
          onClick={() => onExportCsv('reviews')}
        >
          {busy === 'reviews' ? <LoaderCircle aria-hidden className="animate-spin" /> : <Download aria-hidden />}
          Reviews (CSV)
        </Button>
      </div>
      {error ? <Alert variant="error">{error}</Alert> : null}
      <div className="space-y-2 border-t border-border pt-4">
        <h3 className="text-sm font-semibold">Erase my revision data</h3>
        <p className="text-sm text-muted-foreground">
          Deletes your cards, decks, review history, stats and settings for revision. This cannot be undone.
        </p>
        <Button variant="danger" onClick={onErase}>
          <Trash2 aria-hidden />
          Erase everything
        </Button>
      </div>
    </section>
  )
}
