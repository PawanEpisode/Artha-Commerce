import * as React from 'react'

import { presetArt } from '../../avatars/presets'
import { AVATAR_PRESET_KEYS } from '../../avatars/presets'
import { Camera, LoaderCircle, Trash2, Upload } from '../../icons'
import { ACCEPTED_TYPES } from '../../lib/image'
import { cn } from '../../lib/utils'
import { Avatar } from './avatar'
import { Button } from './button'
import { Tabs, TabsContent, TabsList, TabsTrigger } from './tabs'

export interface AvatarPickerProps {
  /** Currently stored preset key, if any (highlights it). */
  presetKey: string | null
  hasPhoto: boolean
  /** False hides the upload tab (the `profile_avatar` flag is off). */
  uploadEnabled: boolean
  /** Why upload is unavailable right now (offline), or null. */
  uploadDisabledReason?: string | null
  busy?: boolean
  /** Inline error from choosing a file (type, size, small). */
  fileError?: string | null
  /** True while the chosen file is being decoded. */
  preparing?: boolean
  onFile: (file: File) => void
  onPreset: (key: string) => void
  onRemove?: () => void
  className?: string
}

/** Upload tab and a grid of the 24 presets. Presentational: the container owns files, crop and requests. */
export function AvatarPicker({
  presetKey,
  hasPhoto,
  uploadEnabled,
  uploadDisabledReason,
  busy,
  fileError,
  preparing,
  onFile,
  onPreset,
  onRemove,
  className,
}: AvatarPickerProps) {
  const input = React.useRef<HTMLInputElement>(null)
  const [tab, setTab] = React.useState(uploadEnabled ? 'upload' : 'presets')
  const uploadBlocked = Boolean(uploadDisabledReason) || busy || preparing

  const presets = (
    <div role="group" aria-label="Choose an avatar" className="grid grid-cols-4 gap-3 sm:grid-cols-6">
      {AVATAR_PRESET_KEYS.map((key) => {
        const selected = key === presetKey
        return (
          <button
            key={key}
            type="button"
            aria-pressed={selected}
            aria-label={`Avatar ${Number(key.slice(1))}: ${presetArt(key)?.name ?? key}`}
            disabled={busy}
            onClick={() => onPreset(key)}
            className={cn(
              'grid size-14 place-items-center justify-self-center rounded-full outline-none focus-visible:ring-[3px] focus-visible:ring-ring/40 disabled:opacity-50',
              selected && 'ring-2 ring-primary ring-offset-2 ring-offset-card',
            )}
          >
            <Avatar size={44} presetKey={key} decorative className="size-12" />
          </button>
        )
      })}
    </div>
  )

  if (!uploadEnabled) return <div className={className}>{presets}</div>

  return (
    <Tabs value={tab} onValueChange={setTab} className={className}>
      <TabsList>
        <TabsTrigger value="upload">Upload</TabsTrigger>
        <TabsTrigger value="presets">Avatars</TabsTrigger>
      </TabsList>
      <TabsContent value="upload" className="mt-4 space-y-3">
        <input
          ref={input}
          type="file"
          hidden
          accept={ACCEPTED_TYPES.join(',')}
          onChange={(e) => {
            const file = e.target.files?.[0]
            e.target.value = '' // choosing the same file again must still fire
            if (file) onFile(file)
          }}
        />
        <div className="flex flex-wrap items-center gap-3">
          <Button onClick={() => input.current?.click()} disabled={uploadBlocked}>
            {preparing ? (
              <LoaderCircle className="animate-spin" aria-hidden />
            ) : hasPhoto ? (
              <Camera aria-hidden />
            ) : (
              <Upload aria-hidden />
            )}
            {preparing ? 'Preparing your photo' : hasPhoto ? 'Replace photo' : 'Add a photo'}
          </Button>
          {hasPhoto && onRemove ? (
            <Button variant="ghost" onClick={onRemove} disabled={busy}>
              <Trash2 aria-hidden /> Remove photo
            </Button>
          ) : null}
        </div>
        <p className="text-sm text-muted-foreground">
          {uploadDisabledReason ?? 'JPG, PNG or WebP, up to 10 MB. You can crop it next.'}
        </p>
        {fileError ? (
          <p role="alert" className="text-sm font-medium text-destructive">
            {fileError}
          </p>
        ) : null}
      </TabsContent>
      <TabsContent value="presets" className="mt-4">
        {presets}
      </TabsContent>
    </Tabs>
  )
}
