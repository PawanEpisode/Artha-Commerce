import { Alert, Button, Card, Download, Trash2, UsageBar } from '@artha/design-system'

import { formatBytes } from '../lib/format'
import type { Usage } from '../lib/types'

interface UsageSectionProps {
  /** Missing while the numbers load, or when the notes feature is off for this student (export and delete still work). */
  usage?: Usage
  onExport: () => void
  exporting: boolean
  onDeleteAll: () => void
}

/** What the student is using (storage, notes, tags) and the two things they own: export everything, delete everything. */
export function UsageSection({ usage, onExport, exporting, onDeleteAll }: UsageSectionProps) {
  const mb = (n: number) => `${formatBytes(n * 1024 * 1024)}`
  return (
    <div className="space-y-6">
      {usage ? (
        <Card className="space-y-4 p-6">
          <h2 className="font-display text-xl font-bold">Your space</h2>
          <UsageBar
            label="Storage"
            used={usage.used.storage_bytes}
            limit={usage.limits.max_storage_mb * 1024 * 1024}
            format={formatBytes}
            fullText="Storage full"
          />
          <UsageBar
            label="Notes"
            used={usage.used.notes}
            limit={usage.limits.max_notes}
            fullText="Note limit reached"
          />
          <UsageBar label="Tags" used={usage.used.tags} limit={usage.limits.max_tags} fullText="Tag limit reached" />
          <p className="text-sm text-muted-foreground">
            One note can hold up to {usage.limits.max_note_chars.toLocaleString('en-IN')} characters and{' '}
            {usage.limits.max_note_images} images. Your plan is {usage.plan}, with {mb(usage.limits.max_storage_mb)} of
            storage.
          </p>
        </Card>
      ) : null}
      <Card className="space-y-3 p-6">
        <h2 className="font-display text-xl font-bold">Export</h2>
        <p className="text-sm text-muted-foreground">Download every note with its versions and tags as one file.</p>
        <Button variant="outline" onClick={onExport} disabled={exporting}>
          <Download aria-hidden /> {exporting ? 'Preparing…' : 'Export all my notes'}
        </Button>
      </Card>
      <Card className="space-y-3 p-6">
        <h2 className="font-display text-xl font-bold">Delete everything</h2>
        <Alert variant="error">
          Deleting removes all your notes, versions, tags and images for good. It cannot be undone.
        </Alert>
        <Button variant="danger" onClick={onDeleteAll}>
          <Trash2 aria-hidden /> Delete all my notes
        </Button>
      </Card>
    </div>
  )
}
