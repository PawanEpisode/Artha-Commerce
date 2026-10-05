import { api, apiUpload } from '~/lib/api'

import {
  type Avatar,
  avatarSchema,
  type Bootstrap,
  bootstrapSchema,
  type Completion,
  completionSchema,
  type OnboardingState,
  onboardingStateSchema,
} from './types'

const json = (body: unknown) => JSON.stringify(body)

export const getBootstrap = async (): Promise<Bootstrap> => bootstrapSchema.parse(await api<unknown>('/me/'))

export const patchName = async (fullName: string): Promise<Bootstrap> =>
  bootstrapSchema.parse(await api<unknown>('/me/', { method: 'PATCH', body: json({ full_name: fullName }) }))

export const putPreset = async (key: string): Promise<Avatar> =>
  avatarSchema.parse(await api<unknown>('/me/avatar/preset/', { method: 'PUT', body: json({ key }) }))

export const deleteAvatar = async (): Promise<Avatar> =>
  avatarSchema.parse(await api<unknown>('/me/avatar/', { method: 'DELETE' }))

export async function uploadAvatar(
  photo: Blob,
  options: { signal?: AbortSignal; onProgress?: (percent: number) => void },
): Promise<Avatar> {
  const form = new FormData()
  form.append('file', photo, 'avatar.webp')
  return avatarSchema.parse(await apiUpload<unknown>('/me/avatar/', form, options))
}

export const exportAccount = () => api<unknown>('/me/export/')

export const deleteAccount = (confirm: string) => api<void>('/me/', { method: 'DELETE', body: json({ confirm }) })

export const getOnboarding = async (): Promise<OnboardingState> =>
  onboardingStateSchema.parse(await api<unknown>('/me/onboarding/'))

export const putStep = async (key: string, body: unknown): Promise<OnboardingState> =>
  onboardingStateSchema.parse(await api<unknown>(`/me/onboarding/steps/${key}/`, { method: 'PUT', body: json(body) }))

export const skipStep = async (key: string): Promise<OnboardingState> =>
  onboardingStateSchema.parse(await api<unknown>(`/me/onboarding/steps/${key}/skip/`, { method: 'POST', body: '{}' }))

export const completeOnboarding = async (): Promise<Completion> =>
  completionSchema.parse(await api<unknown>('/me/onboarding/complete/', { method: 'POST', body: '{}' }))
