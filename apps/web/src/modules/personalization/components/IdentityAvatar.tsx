import { Avatar, type AvatarSize } from '@artha/design-system'

import { useAuth } from '~/modules/auth'

import { useBootstrap } from '../hooks/useBootstrap'

/**
 * The signed-in student's avatar. Until the profile arrives it is a fixed-size placeholder, then the upload, the
 * preset, or initials. Decorative when the name is printed next to it.
 */
export function IdentityAvatar({ size = 44, decorative = false }: { size?: AvatarSize; decorative?: boolean }) {
  const { user } = useAuth()
  const boot = useBootstrap()
  const data = boot.data
  const meta = (user?.user_metadata ?? {}) as { full_name?: string; name?: string }
  const name = data?.full_name || meta.full_name || meta.name || ''
  return (
    <Avatar
      size={size}
      name={name}
      email={data?.email ?? user?.email}
      seed={user?.id}
      urls={data?.avatar.urls}
      presetKey={data?.avatar.kind === 'preset' ? data.avatar.preset_key : null}
      version={data?.avatar.version}
      loading={boot.isPending && !data}
      decorative={decorative}
    />
  )
}
