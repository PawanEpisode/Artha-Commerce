import { Button, ButtonLink, CircleAlert, Container, Download, Hourglass, RefreshCw, Send } from '@artha/design-system'

export interface ReaderErrorStateProps {
  title?: string
  /** `info` for "not ready yet" (no alarm), `error` (default) for a failure. */
  variant?: 'error' | 'info'
  message: string
  /** Shown to quote when reporting; the API's request id when it sent one. */
  requestId?: string
  onRetry?: () => void
  /** The signed link of the original file, for "Download original". */
  downloadUrl?: string | null
  onReport?: () => void
  onBack: () => void
  backLabel?: string
}

/** Full-page state when the file cannot be opened at all (PRD 7.3: "We could not open this file"). */
export function ReaderErrorState({
  title = 'We could not open this file',
  variant = 'error',
  message,
  requestId,
  onRetry,
  downloadUrl,
  onReport,
  onBack,
  backLabel = 'Back to library',
}: ReaderErrorStateProps) {
  return (
    <Container className="grid min-h-dvh max-w-lg place-items-center py-12">
      <div role={variant === 'error' ? 'alert' : 'status'} className="grid gap-4 text-center">
        {variant === 'error' ? (
          <CircleAlert className="mx-auto size-10 text-destructive" aria-hidden />
        ) : (
          <Hourglass className="mx-auto size-10 text-muted-foreground" aria-hidden />
        )}
        <h1 className="text-xl font-semibold">{title}</h1>
        <p className="text-muted-foreground">{message}</p>
        {requestId ? <p className="text-xs text-muted-foreground">Request id: {requestId}</p> : null}
        <div className="flex flex-wrap justify-center gap-2">
          {onRetry ? (
            <Button onClick={onRetry}>
              <RefreshCw aria-hidden />
              Retry
            </Button>
          ) : null}
          {downloadUrl ? (
            <ButtonLink variant="outline" href={downloadUrl} rel="noopener noreferrer" download>
              <Download aria-hidden />
              Download original
            </ButtonLink>
          ) : null}
          {onReport ? (
            <Button variant="outline" onClick={onReport}>
              <Send aria-hidden />
              Report a problem
            </Button>
          ) : null}
          <Button variant="ghost" onClick={onBack}>
            {backLabel}
          </Button>
        </div>
      </div>
    </Container>
  )
}
