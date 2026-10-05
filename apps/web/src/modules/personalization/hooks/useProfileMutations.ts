import { type QueryClient, useMutation, useQueryClient } from '@tanstack/react-query'
import { useRef, useState } from 'react'

import { track } from '~/modules/observability'

import { deleteAvatar, patchName, putPreset, uploadAvatar } from '../lib/api'
import { personalizationKeys } from '../lib/keys'
import { notify } from '../lib/notify'
import type { Avatar, Bootstrap } from '../lib/types'

/** Every bootstrap entry (one per user id) gets the new avatar at once, so header and Account change together. */
function applyAvatar(qc: QueryClient, avatar: Avatar) {
  qc.setQueriesData<Bootstrap>({ queryKey: personalizationKeys.bootstrap }, (old) => (old ? { ...old, avatar } : old))
}

export function useUpdateName() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: patchName,
    onSuccess: (bootstrap) => {
      qc.setQueriesData({ queryKey: personalizationKeys.bootstrap }, bootstrap)
      notify.nameSaved()
    },
  })
}

export function useChoosePreset() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: putPreset,
    onSuccess: (avatar) => {
      applyAvatar(qc, avatar)
      track('avatar_preset_selected', { preset_key: avatar.preset_key })
      notify.avatarChosen()
    },
    onError: (error) => notify.failed(error, 'We could not change your avatar. Please try again.', 'profile-avatar'),
  })
}

export function useRemoveAvatar() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: deleteAvatar,
    onSuccess: (avatar) => {
      applyAvatar(qc, avatar)
      track('avatar_removed')
      notify.photoRemoved()
    },
    onError: (error) => notify.failed(error, 'We could not remove your photo. Please try again.', 'profile-avatar'),
  })
}

/** Upload with progress and cancel. The caller shows errors inside the crop dialog, so there is no error toast here. */
export function useUploadAvatar() {
  const qc = useQueryClient()
  const controller = useRef<AbortController | null>(null)
  const [progress, setProgress] = useState<number | null>(null)

  const mutation = useMutation({
    mutationFn: (photo: Blob) => {
      controller.current = new AbortController()
      setProgress(0)
      return uploadAvatar(photo, { signal: controller.current.signal, onProgress: setProgress })
    },
    onSuccess: (avatar) => {
      applyAvatar(qc, avatar)
      notify.photoUpdated()
    },
    onSettled: () => setProgress(null),
  })

  return {
    ...mutation,
    progress,
    cancel: () => controller.current?.abort(),
  }
}
