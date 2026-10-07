import * as React from 'react'

import { CircleAlert, FileUp, Upload } from '../../icons'
import { cn } from '../../lib/utils'

export type FileRejectionReason = 'type' | 'size' | 'count'
export interface FileRejection {
  file: File
  reason: FileRejectionReason
}

/** True when the file matches an `accept` list such as ".pdf,image/*,application/pdf". An empty list accepts anything. */
export function matchesAccept(file: Pick<File, 'name' | 'type'>, accept?: string): boolean {
  const tokens = (accept ?? '')
    .split(',')
    .map((t) => t.trim().toLowerCase())
    .filter(Boolean)
  if (tokens.length === 0) return true
  const name = file.name.toLowerCase()
  const type = file.type.toLowerCase()
  return tokens.some((token) => {
    if (token.startsWith('.')) return name.endsWith(token)
    if (token.endsWith('/*')) return type.startsWith(token.slice(0, -1))
    return type === token
  })
}

/** Splits dropped or picked files into the ones to hand on and the ones turned away, with the reason for each. */
export function sortFiles(
  files: ReadonlyArray<File>,
  { accept, maxSizeBytes, multiple }: { accept?: string; maxSizeBytes?: number; multiple?: boolean },
): { accepted: File[]; rejected: FileRejection[] } {
  const accepted: File[] = []
  const rejected: FileRejection[] = []
  for (const file of files) {
    if (!matchesAccept(file, accept)) rejected.push({ file, reason: 'type' })
    else if (maxSizeBytes !== undefined && file.size > maxSizeBytes) rejected.push({ file, reason: 'size' })
    else if (!multiple && accepted.length >= 1) rejected.push({ file, reason: 'count' })
    else accepted.push(file)
  }
  return { accepted, rejected }
}

export interface FileDropzoneProps extends Omit<
  React.ComponentProps<'div'>,
  'onDrop' | 'onChange' | 'children' | 'title'
> {
  /** Receives the files that passed the type and size checks. The component does no uploading. */
  onFiles: (files: File[]) => void
  /** Receives the files that did not, for example to count them. The visible message is shown by the component. */
  onReject?: (rejections: FileRejection[]) => void
  /** Same syntax as the `accept` attribute of an input: ".pdf,application/pdf". */
  accept?: string
  maxSizeBytes?: number
  multiple?: boolean
  /** The call to action. */
  title?: string
  /** Accepted types and limits in words, always visible: "PDF, up to 200 MB". */
  hint?: string
  /** Wording for turned-away files. The defaults are generic; pass a sentence that names the real types and limits. */
  messages?: Partial<Record<FileRejectionReason, string>>
  /** An error from outside (the server said no). Shown below the drop area and linked with `aria-describedby`. */
  error?: string
  disabled?: boolean
  /** Why it is disabled ("Storage full. Free up space to add more."). Shown, and read out, when `disabled`. */
  reason?: string
  /** Accessible name of the file input. Defaults to the title. */
  inputLabel?: string
}

const DEFAULT_MESSAGES: Record<FileRejectionReason, string> = {
  type: 'That file type is not accepted.',
  size: 'That file is too large.',
  count: 'Add one file at a time.',
}

function hasFiles(event: React.DragEvent) {
  return Array.from(event.dataTransfer?.types ?? []).includes('Files')
}

/**
 * Drag files in, or click or press Enter or Space to pick them. A visually hidden but focusable file input does the
 * keyboard and screen reader work; the visible area is its label. Shows accepted types and limits, a drag-over state
 * that changes shape and words (not only colour), an error line and a disabled state with its reason. One file unless
 * `multiple`.
 */
export function FileDropzone({
  onFiles,
  onReject,
  accept,
  maxSizeBytes,
  multiple = false,
  title = multiple ? 'Drop files here or choose files' : 'Drop a file here or choose a file',
  hint,
  messages,
  error,
  disabled = false,
  reason,
  inputLabel,
  className,
  id,
  ...props
}: FileDropzoneProps) {
  const reactId = React.useId()
  const inputId = id ?? `${reactId}-input`
  const hintId = `${inputId}-hint`
  const errorId = `${inputId}-error`
  const reasonId = `${inputId}-reason`
  const [dragging, setDragging] = React.useState(false)
  const [localError, setLocalError] = React.useState<string | null>(null)
  const depth = React.useRef(0)

  const shownError = error ?? localError
  const describedBy =
    [hint ? hintId : null, disabled && reason ? reasonId : null, shownError ? errorId : null]
      .filter(Boolean)
      .join(' ') || undefined

  const handle = (list: ArrayLike<File> | null | undefined) => {
    const files = Array.from(list ?? [])
    if (disabled || files.length === 0) return
    const { accepted, rejected } = sortFiles(files, { accept, maxSizeBytes, multiple })
    const [firstRejected] = rejected
    if (firstRejected) {
      setLocalError({ ...DEFAULT_MESSAGES, ...messages }[firstRejected.reason])
      onReject?.(rejected)
    } else {
      setLocalError(null)
    }
    if (accepted.length > 0) onFiles(accepted)
  }

  const endDrag = () => {
    depth.current = 0
    setDragging(false)
  }

  return (
    <div
      data-slot="file-dropzone"
      data-dragging={dragging || undefined}
      data-disabled={disabled || undefined}
      className={cn('space-y-2', className)}
      onDragEnter={(event) => {
        if (disabled || !hasFiles(event)) return
        event.preventDefault()
        depth.current += 1
        setDragging(true)
      }}
      onDragOver={(event) => {
        if (disabled || !hasFiles(event)) return
        event.preventDefault() // required, or the browser refuses the drop
        event.dataTransfer.dropEffect = 'copy'
      }}
      onDragLeave={() => {
        depth.current = Math.max(0, depth.current - 1)
        if (depth.current === 0) setDragging(false)
      }}
      onDrop={(event) => {
        if (disabled) return
        event.preventDefault()
        endDrag()
        handle(event.dataTransfer?.files)
      }}
      {...props}
    >
      <input
        id={inputId}
        type="file"
        className="peer sr-only"
        accept={accept}
        multiple={multiple}
        disabled={disabled}
        aria-label={inputLabel}
        aria-describedby={describedBy}
        aria-invalid={shownError ? true : undefined}
        onChange={(event) => {
          handle(event.currentTarget.files)
          event.currentTarget.value = '' // choosing the same file again must still fire
        }}
      />
      <label
        htmlFor={inputId}
        className={cn(
          'flex min-h-40 w-full cursor-pointer flex-col items-center justify-center gap-2 rounded-2xl border-2 border-dashed border-input bg-card p-6 text-center transition-colors peer-focus-visible:ring-[3px] peer-focus-visible:ring-ring/60 peer-focus-visible:ring-offset-2 peer-focus-visible:ring-offset-background hover:bg-muted motion-reduce:transition-none',
          dragging && 'border-solid border-primary bg-secondary',
          shownError && !dragging && 'border-error-border',
          disabled && 'cursor-not-allowed opacity-60 hover:bg-card',
        )}
      >
        {dragging ? (
          <FileUp aria-hidden className="size-8 text-primary" />
        ) : (
          <Upload aria-hidden className="size-8 text-muted-foreground" />
        )}
        <span className="max-w-full text-base font-semibold break-words">{dragging ? 'Release to add' : title}</span>
        {hint ? (
          <span id={hintId} aria-hidden className="max-w-full text-sm break-words text-muted-foreground">
            {hint}
          </span>
        ) : null}
      </label>
      {disabled && reason ? (
        <p id={reasonId} className="text-sm font-medium text-foreground">
          {reason}
        </p>
      ) : null}
      {shownError ? (
        <p id={errorId} role="alert" className="flex items-start gap-1.5 text-sm font-medium text-error-fg">
          <CircleAlert aria-hidden className="mt-0.5 size-4 shrink-0" />
          <span className="min-w-0 break-words">{shownError}</span>
        </p>
      ) : null}
    </div>
  )
}
