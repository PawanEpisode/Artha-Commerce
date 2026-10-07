import { useCallback, useRef, useState } from 'react'

import { ApiError } from '~/lib/api'
import type { PickedImage } from '~/lib/richtext'

import { uploadNoteImage } from '../lib/api'
import { quotaExceeded } from '../lib/errors'

/** Words for a failed image upload. */
export function uploadErrorText(error: unknown): string {
  if (quotaExceeded(error)) return 'Your notes storage is full. Delete something you no longer need, then try again.'
  if (error instanceof ApiError && error.status === 415)
    return 'That file type is not supported. Use PNG, JPEG or WebP.'
  if (error instanceof ApiError && error.status === 413) return 'That image is too large. Choose a smaller one.'
  return 'The image could not be uploaded. Check your connection and try again.'
}

/**
 * Drives the image dialog for the editor: `onPickImage` opens it and resolves with the uploaded attachment and its
 * description, or null when the student cancels. The upload runs in the dialog so a failure keeps the form filled in.
 */
export function useImagePicker() {
  const [open, setOpenState] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string>()
  const resolver = useRef<((value: PickedImage | null) => void) | null>(null)

  const finish = (value: PickedImage | null) => {
    resolver.current?.(value)
    resolver.current = null
  }

  const onPickImage = useCallback(
    () =>
      new Promise<PickedImage | null>((resolve) => {
        resolver.current = resolve
        setError(undefined)
        setOpenState(true)
      }),
    [],
  )

  const onSubmit = async (file: File, alt: string) => {
    setBusy(true)
    setError(undefined)
    try {
      const attachmentId = await uploadNoteImage(file)
      finish({ attachmentId, alt })
      setOpenState(false)
    } catch (e) {
      setError(uploadErrorText(e))
    } finally {
      setBusy(false)
    }
  }

  const onOpenChange = (next: boolean) => {
    if (!next) finish(null)
    setOpenState(next)
  }

  return { onPickImage, dialog: { open, onOpenChange, busy, error, onSubmit } }
}
