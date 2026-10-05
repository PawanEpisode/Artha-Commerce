import * as React from 'react'

import { presetArt } from '../../avatars/presets'
import { avatarColourIndex, initialsOf } from '../../lib/initials'
import { cn } from '../../lib/utils'

export type AvatarSize = 24 | 32 | 44 | 96

const SIZE: Record<AvatarSize, string> = {
  24: 'size-6 text-[10px]',
  32: 'size-8 text-xs',
  44: 'size-11 text-sm',
  96: 'size-24 text-3xl',
}

export interface AvatarProps extends Omit<React.ComponentProps<'span'>, 'children'> {
  size?: AvatarSize
  /** The student's name and email: initials come from them. Both may be empty while loading. */
  name?: string | null
  email?: string | null
  /** Stable seed for the colour, the user id. The colour never changes when the name does. */
  seed?: string
  /** Uploaded photo, in two renditions: the 128 px one is used up to 44 px, the 512 px one above. */
  urls?: { small: string; large: string } | null
  /** Preset artwork key (`p01` to `p24`). Used when there is no photo, or when the photo fails to load. */
  presetKey?: string | null
  /** Photo version: a new version remounts the image so a replaced photo never shows stale. */
  version?: number
  /** Fixed-size placeholder while the profile loads (no layout shift). */
  loading?: boolean
  /** Decorative (next to the name): hides it from assistive tech. */
  decorative?: boolean
}

/**
 * The student's picture: uploaded photo, else preset artwork, else generated initials. A photo that fails to load
 * drops to initials without a broken-image icon. Colours are tokens (`--avatar-1..8`) so every theme stays readable.
 */
export function Avatar({
  size = 44,
  name,
  email,
  seed,
  urls,
  presetKey,
  version = 0,
  loading = false,
  decorative = false,
  className,
  style,
  ...props
}: AvatarProps) {
  const [failedUrl, setFailedUrl] = React.useState<string | null>(null)
  const src = urls ? (size >= 96 ? urls.large : urls.small) : null
  const showImage = Boolean(src) && src !== failedUrl
  const preset = !showImage && presetKey ? presetArt(presetKey) : null
  const colour = preset?.colour ?? avatarColourIndex(seed || email || name || '')
  const label = name?.trim() || 'Profile picture'

  if (loading) {
    return (
      <span
        data-slot="avatar"
        aria-hidden
        className={cn(
          'inline-block shrink-0 animate-pulse rounded-full bg-muted motion-reduce:animate-none',
          SIZE[size],
          className,
        )}
      />
    )
  }

  return (
    <span
      data-slot="avatar"
      data-kind={showImage ? 'photo' : preset ? 'preset' : 'initials'}
      role={decorative ? undefined : 'img'}
      aria-label={decorative ? undefined : label}
      aria-hidden={decorative || undefined}
      className={cn(
        'relative inline-flex shrink-0 items-center justify-center overflow-hidden rounded-full font-bold ring-1 ring-border select-none',
        SIZE[size],
        className,
      )}
      style={{ background: `var(--avatar-${colour})`, color: `var(--avatar-${colour}-fg)`, ...style }}
      {...props}
    >
      {showImage ? (
        <img
          key={`${src}-${version}`}
          src={src ?? undefined}
          alt=""
          width={size}
          height={size}
          decoding="async"
          onError={() => setFailedUrl(src)}
          className="size-full object-cover"
        />
      ) : preset ? (
        <svg viewBox="0 0 64 64" aria-hidden className="size-full">
          {preset.art}
        </svg>
      ) : (
        <span aria-hidden>{initialsOf(name, email)}</span>
      )}
    </span>
  )
}
