import { ConflictSheet } from '../components/ConflictSheet'
import { useUiScope } from './annotation-scope'

/**
 * Two devices changed the same comment (FR-F03-62). One parked conflict at a time, with the same sheet as notes: Keep
 * mine, Keep theirs or Keep both. Other marks were never held up by it.
 */
export function MarkConflictContainer() {
  const ui = useUiScope()
  if (!ui) return null
  const { current, busy, resolve } = ui.conflicts
  if (!current) return null
  const mine = current.detail.mine.comment ?? ''
  return (
    <ConflictSheet
      open={ui.conflictOpen}
      onOpenChange={ui.setConflictOpen}
      noun="mark"
      theirs={{ title: '', body_md: current.detail.theirs.comment, updated_at: current.detail.theirs_updated_at }}
      mine={{ title: '', body: mine }}
      deviceLabel={current.detail.device_label ?? undefined}
      busy={busy}
      onResolve={(resolution) => {
        void resolve(current, resolution).then((ok) => {
          if (ok && ui.conflicts.parked.length <= 1) ui.setConflictOpen(false)
        })
      }}
    />
  )
}
