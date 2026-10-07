import { Alert, Button, X } from '@artha/design-system'

export interface LargeDocumentNoticeProps {
  onDismiss: () => void
}

/** The one-line notice of large-document mode, shown once per document (PRD 5.5). */
export function LargeDocumentNotice({ onDismiss }: LargeDocumentNoticeProps) {
  return (
    <Alert variant="info" data-slot="large-document-notice">
      <div className="flex items-start gap-2">
        <p className="min-w-0 flex-1">Large PDF: pages load as you scroll, and search runs on our servers.</p>
        <Button
          variant="ghost"
          size="icon"
          className="-my-2 -mr-2 size-11"
          onClick={onDismiss}
          aria-label="Dismiss notice"
        >
          <X aria-hidden />
        </Button>
      </div>
    </Alert>
  )
}
