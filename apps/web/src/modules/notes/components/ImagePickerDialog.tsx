import {
  Alert,
  Button,
  Checkbox,
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogTitle,
  Label,
  TextField,
} from '@artha/design-system'
import { useRef, useState } from 'react'

import { IMAGE_TYPES } from '../lib/api'

export const MAX_IMAGE_BYTES = 10 * 1024 * 1024

/** The first thing wrong with a chosen image file, in words, or null. Pure so it is tested without a browser. */
export function imageProblem(file: { type: string; size: number }): string | null {
  if (!(IMAGE_TYPES as ReadonlyArray<string>).includes(file.type)) return 'Choose a PNG, JPEG or WebP image.'
  if (file.size > MAX_IMAGE_BYTES) return 'That image is larger than 10 MB. Choose a smaller one.'
  return null
}

interface ImagePickerDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  busy: boolean
  /** A failure of the upload itself, in words. */
  error?: string
  onSubmit: (file: File, alt: string) => void
}

/**
 * Adds an image to a note. Every image needs a description for screen readers (alt text); the only way past it is to
 * say the image is decorative, which is an explicit choice, never a default.
 */
export function ImagePickerDialog({ open, onOpenChange, busy, error, onSubmit }: ImagePickerDialogProps) {
  const [file, setFile] = useState<File | null>(null)
  const [alt, setAlt] = useState('')
  const [decorative, setDecorative] = useState(false)
  const [fileError, setFileError] = useState<string>()
  const input = useRef<HTMLInputElement>(null)
  const altMissing = !decorative && alt.trim() === ''
  const ready = file !== null && !fileError && !altMissing && !busy

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogTitle>Add an image</DialogTitle>
        <DialogDescription>
          PNG, JPEG or WebP, up to 10 MB. Describe what it shows for people who cannot see it.
        </DialogDescription>
        <form
          className="mt-4 space-y-4"
          onSubmit={(event) => {
            event.preventDefault()
            if (file && ready) onSubmit(file, decorative ? '' : alt.trim())
          }}
        >
          <div className="grid gap-2">
            <label htmlFor="note-image-file" className="text-sm font-medium">
              Image file
            </label>
            <input
              ref={input}
              id="note-image-file"
              type="file"
              accept={IMAGE_TYPES.join(',')}
              aria-describedby={fileError ? 'note-image-file-error' : undefined}
              className="block min-h-11 w-full rounded-lg border border-input bg-card p-2 text-sm file:mr-3 file:min-h-9 file:rounded-md file:border-0 file:bg-secondary file:px-3 file:text-secondary-foreground"
              onChange={(event) => {
                const chosen = event.target.files?.[0] ?? null
                setFile(chosen)
                setFileError(chosen ? (imageProblem(chosen) ?? undefined) : undefined)
              }}
            />
            {fileError ? (
              <p id="note-image-file-error" role="alert" className="text-sm text-destructive">
                {fileError}
              </p>
            ) : null}
          </div>
          <TextField
            label="Description (alt text)"
            value={alt}
            disabled={decorative}
            onChange={(e) => setAlt(e.target.value)}
            hint="For example: Journal entry for a credit sale."
          />
          <div className="flex items-center gap-3">
            <Checkbox
              id="note-image-decorative"
              checked={decorative}
              onCheckedChange={(v) => setDecorative(v === true)}
            />
            <Label htmlFor="note-image-decorative">This image is only decoration</Label>
          </div>
          {error ? (
            <Alert variant="error">
              <span>{error}</span>
            </Alert>
          ) : null}
          <div className="flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
            <DialogClose asChild>
              <Button type="button" variant="ghost">
                Cancel
              </Button>
            </DialogClose>
            <Button type="submit" disabled={!ready}>
              {busy ? 'Uploading…' : 'Add image'}
            </Button>
          </div>
          {file && altMissing ? (
            <p className="text-sm text-muted-foreground">
              Add a description, or tick that the image is only decoration.
            </p>
          ) : null}
        </form>
      </DialogContent>
    </Dialog>
  )
}
