import {
  AvatarPicker,
  Button,
  bytesBucket,
  checkImageFile,
  checkImageSize,
  cropToBlob,
  Dialog,
  DialogContent,
  DialogDescription,
  DialogTitle,
  IMAGE_PROBLEM_TEXT,
  ImageCropDialog,
  type ImageFileProblem,
  loadImage,
  type PixelCrop,
} from '@artha/design-system'
import { useEffect, useState } from 'react'

import { ApiError } from '~/lib/api'
import { track, useFeatureFlag } from '~/modules/observability'

import { useOnline } from '../hooks/useOnline'
import { useChoosePreset, useRemoveAvatar, useUploadAvatar } from '../hooks/useProfileMutations'
import { describeUploadError } from '../lib/avatarErrors'
import type { Avatar } from '../lib/types'

interface Chosen {
  url: string
}

/**
 * Everything for changing the picture: the picker (upload or one of 24 avatars), the crop dialog with its upload
 * states, and the remove confirmation. Used by the Profile section and the onboarding photo step, so both behave alike.
 */
export function AvatarEditor({ avatar, onChanged }: { avatar: Avatar; onChanged?: () => void }) {
  const online = useOnline()
  const uploadEnabled = useFeatureFlag('profile_avatar')
  const preset = useChoosePreset()
  const remove = useRemoveAvatar()
  const upload = useUploadAvatar()

  const [chosen, setChosen] = useState<Chosen | null>(null)
  const [preparing, setPreparing] = useState(false)
  const [fileError, setFileError] = useState<string | null>(null)
  const [uploadError, setUploadError] = useState<string | null>(null)
  const [confirmRemove, setConfirmRemove] = useState(false)

  // Free the object URL when the dialog closes or the component goes away.
  useEffect(() => () => (chosen ? URL.revokeObjectURL(chosen.url) : undefined), [chosen])

  async function onFile(file: File) {
    setFileError(null)
    const problem: ImageFileProblem | null = checkImageFile(file)
    if (problem) {
      track('avatar_upload_failed', { reason: problem })
      return setFileError(IMAGE_PROBLEM_TEXT[problem])
    }
    setPreparing(true)
    try {
      const image = await loadImage(file)
      const tooSmall = checkImageSize(image.width, image.height)
      if (tooSmall) {
        URL.revokeObjectURL(image.url)
        setFileError(IMAGE_PROBLEM_TEXT[tooSmall])
        return track('avatar_upload_failed', { reason: 'small' })
      }
      setUploadError(null)
      setChosen({ url: image.url })
    } catch {
      setFileError(IMAGE_PROBLEM_TEXT.unreadable)
    } finally {
      setPreparing(false)
    }
  }

  async function onSave(area: PixelCrop, zoom: number) {
    if (!chosen) return
    setUploadError(null)
    const started = performance.now()
    try {
      const blob = await cropToBlob(chosen.url, area)
      await upload.mutateAsync(blob)
      track('avatar_uploaded', {
        bytes_bucket: bytesBucket(blob.size),
        ms: Math.round(performance.now() - started),
        crop_zoom_bucket: Math.round(zoom),
      })
      setChosen(null)
      onChanged?.()
    } catch (error) {
      if (error instanceof DOMException && error.name === 'AbortError') return
      const { reason, message } = describeUploadError(error)
      track('avatar_upload_failed', { reason })
      setUploadError(error instanceof ApiError || reason !== 'server' ? message : IMAGE_PROBLEM_TEXT.unreadable)
    }
  }

  function closeCrop() {
    upload.cancel()
    setChosen(null)
    setUploadError(null)
  }

  return (
    <>
      <AvatarPicker
        presetKey={avatar.kind === 'preset' ? avatar.preset_key : null}
        hasPhoto={avatar.kind === 'upload'}
        uploadEnabled={uploadEnabled}
        uploadDisabledReason={online ? null : 'Photo upload needs a connection.'}
        busy={preset.isPending || remove.isPending || upload.isPending || !online}
        preparing={preparing}
        fileError={fileError}
        onFile={(file) => void onFile(file)}
        onPreset={(key) => preset.mutate(key, { onSuccess: () => onChanged?.() })}
        onRemove={() => setConfirmRemove(true)}
      />

      <ImageCropDialog
        open={chosen !== null}
        imageUrl={chosen?.url ?? null}
        saving={upload.isPending}
        progress={upload.progress}
        error={uploadError}
        onSave={(area, zoom) => void onSave(area, zoom)}
        onCancel={closeCrop}
      />

      <Dialog open={confirmRemove} onOpenChange={setConfirmRemove}>
        <DialogContent>
          <DialogTitle>Remove your photo?</DialogTitle>
          <DialogDescription>
            Your initials will show instead. The photo is deleted and cannot be restored.
          </DialogDescription>
          <div className="mt-5 flex flex-wrap justify-end gap-3">
            <Button variant="outline" onClick={() => setConfirmRemove(false)}>
              Keep photo
            </Button>
            <Button
              disabled={remove.isPending}
              onClick={() => remove.mutate(undefined, { onSettled: () => setConfirmRemove(false) })}
            >
              Remove photo
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </>
  )
}
