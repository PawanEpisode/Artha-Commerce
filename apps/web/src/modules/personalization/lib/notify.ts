/** Toasts of the personalization module (copy follows the F-16 PRD catalogue, section 5.7). */
import { toast, toastApiError } from '@artha/design-system'

export const notify = {
  nameSaved: () => toast.success('Name saved.', { id: 'profile-name' }),
  photoUpdated: () => toast.success('Profile photo updated.', { id: 'profile-avatar' }),
  avatarChosen: () => toast.success('Avatar updated.', { id: 'profile-avatar' }),
  photoRemoved: () => toast.info('Profile photo removed.', { id: 'profile-avatar' }),
  failed: (error: unknown, fallback: string, id?: string) => toastApiError(error, fallback, id ? { id } : undefined),
}
