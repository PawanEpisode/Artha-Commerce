import {
  Alert,
  Button,
  Check,
  LoaderCircle,
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
  Skeleton,
  StickyNote,
  X,
} from '@artha/design-system'

import { canSaveAsNote, kindText, reasonText, resolvedText } from '../../lib/replace-copy'
import type { AttentionAction, AttentionItem } from '../../lib/replace-types'

interface AttentionSheetProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  title: string
  items: readonly AttentionItem[]
  loading: boolean
  failed: boolean
  /** The item whose decision is on its way to the server. */
  busyId?: string
  online: boolean
  onRetry: () => void
  onResolve: (item: AttentionItem, action: AttentionAction) => void
}

/** "Needs attention": marks from the old edition that could not be placed with confidence. The student decides each one. */
export function AttentionSheet({
  open,
  onOpenChange,
  title,
  items,
  loading,
  failed,
  busyId,
  online,
  onRetry,
  onResolve,
}: AttentionSheetProps) {
  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent side="bottom" className="max-h-[90dvh] overflow-y-auto sm:mx-auto sm:max-w-xl">
        <SheetHeader>
          <SheetTitle>Marks that need your attention</SheetTitle>
          <SheetDescription>
            These marks were on the old edition of “{title}”. We were not sure where they belong in the new one, so we
            did not guess.
          </SheetDescription>
        </SheetHeader>
        {loading ? (
          <div aria-busy="true" className="space-y-3">
            <Skeleton className="h-24 w-full" />
            <Skeleton className="h-24 w-full" />
          </div>
        ) : failed ? (
          <Alert variant="error">
            <span className="flex flex-wrap items-center gap-3">
              <span>We could not load these marks.</span>
              <Button size="sm" variant="outline" onClick={onRetry}>
                Try again
              </Button>
            </span>
          </Alert>
        ) : items.length === 0 ? (
          <p className="text-sm text-muted-foreground">Nothing is waiting. Every mark was placed.</p>
        ) : (
          <ul className="space-y-3">
            {items.map((item) => (
              <li key={item.id} className="space-y-2 rounded-xl border border-border bg-card p-4">
                <p className="text-sm font-semibold">
                  {kindText(item.kind)} · page {item.page} of the old edition
                </p>
                {item.quote ? (
                  <blockquote className="border-l-2 border-border pl-3 text-sm">{item.quote}</blockquote>
                ) : null}
                {item.comment ? <p className="text-sm text-muted-foreground">{item.comment}</p> : null}
                <p className="text-sm text-muted-foreground">{reasonText(item.reason)}</p>
                {item.status === 'open' ? (
                  <div className="flex flex-wrap gap-2">
                    <Button
                      size="sm"
                      className="min-h-11"
                      disabled={!online || busyId === item.id}
                      onClick={() => onResolve(item, 'keep')}
                    >
                      {busyId === item.id ? (
                        <LoaderCircle aria-hidden className="animate-spin" />
                      ) : (
                        <Check aria-hidden />
                      )}{' '}
                      Keep on page {item.page}
                    </Button>
                    {canSaveAsNote(item) ? (
                      <Button
                        size="sm"
                        variant="outline"
                        className="min-h-11"
                        disabled={!online || busyId === item.id}
                        onClick={() => onResolve(item, 'note')}
                      >
                        <StickyNote aria-hidden /> Save as a note
                      </Button>
                    ) : null}
                    <Button
                      size="sm"
                      variant="ghost"
                      className="min-h-11"
                      disabled={!online || busyId === item.id}
                      onClick={() => onResolve(item, 'dismiss')}
                    >
                      <X aria-hidden /> Dismiss
                    </Button>
                  </div>
                ) : (
                  <p className="text-sm font-medium" role="status">
                    {resolvedText(item.status)}
                  </p>
                )}
              </li>
            ))}
          </ul>
        )}
      </SheetContent>
    </Sheet>
  )
}
