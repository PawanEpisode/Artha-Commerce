import {
  Alert,
  AvatarPicker,
  Button,
  bytesBucket,
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
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
  Skeleton,
} from '@artha/design-system'
import { useEffect, useState } from 'react'

import { ApiError } from '~/lib/api'
import { track, useFeatureFlag } from '~/modules/observability'

import { IdentityAvatar } from '../components/IdentityAvatar'
import { NameForm } from '../components/NameForm'
import { useBootstrap } from '../hooks/useBootstrap'
import { useOnline } from '../hooks/useOnline'
import { useChoosePreset, useRemoveAvatar, useUpdateName, useUploadAvatar } from '../hooks/useProfileMutations'
import { describeUploadError } from '../lib/avatarErrors'

interface Chosen {
  url: string
  /** Size of the original file, for the analytics bucket only. */
  bytes: number
}

/** Account page "Profile" section (PRD 5.5): name and picture, with every state of the avatar flow. */
export function ProfileSection() {
  const { data, isPending, isError, refetch } = useBootstrap()
  const online = useOnline()
  const uploadEnabled = useFeatureFlag('profile_avatar')

  const rename = useUpdateName()
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
    if (problem) return setFileError(IMAGE_PROBLEM_TEXT[problem])
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
      setChosen({ url: image.url, bytes: file.size })
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

  const busy = preset.isPending || remove.isPending || upload.isPending

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-lg">Profile</CardTitle>
        <CardDescription>Your name and picture. Only you see them, on this account.</CardDescription>
      </CardHeader>
      <CardContent className="space-y-6">
        {isPending ? (
          <div className="flex items-center gap-4" aria-busy>
            <Skeleton className="size-24 rounded-full" />
            <Skeleton className="h-11 flex-1" />
          </div>
        ) : isError || !data ? (
          <Alert variant="error">
            <div className="space-y-2">
              <p>We could not load your profile.</p>
              <Button size="sm" variant="outline" onClick={() => void refetch()}>
                Try again
              </Button>
            </div>
          </Alert>
        ) : (
          <>
            <div className="flex flex-col gap-5 sm:flex-row sm:items-start">
              <IdentityAvatar size={96} />
              <div className="min-w-0 flex-1">
                <NameForm
                  key={data.full_name}
                  value={data.full_name}
                  pending={rename.isPending}
                  disabled={!online}
                  serverError={nameError(rename.error)}
                  onSave={(name) => rename.mutate(name)}
                />
                {!online ? (
                  <p className="mt-2 text-sm text-muted-foreground">You are offline. Name changes need a connection.</p>
                ) : null}
              </div>
            </div>

            <AvatarPicker
              presetKey={data.avatar.kind === 'preset' ? data.avatar.preset_key : null}
              hasPhoto={data.avatar.kind === 'upload'}
              uploadEnabled={uploadEnabled}
              uploadDisabledReason={online ? null : 'Photo upload needs a connection.'}
              busy={busy || !online}
              preparing={preparing}
              fileError={fileError}
              onFile={(file) => void onFile(file)}
              onPreset={(key) => preset.mutate(key)}
              onRemove={() => setConfirmRemove(true)}
            />
          </>
        )}
      </CardContent>

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
              variant="default"
              disabled={remove.isPending}
              onClick={() => remove.mutate(undefined, { onSettled: () => setConfirmRemove(false) })}
            >
              Remove photo
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </Card>
  )
}

/** The server's message for the name field (400 `invalid`), if that is what failed. */
function nameError(error: unknown): string | undefined {
  if (!(error instanceof ApiError)) return error ? 'We could not save your name. Try again.' : undefined
  const details = (error.body as { error?: { details?: { full_name?: string[] } } } | undefined)?.error?.details
  return details?.full_name?.[0] ?? 'We could not save your name. Try again.'
}
