/**
 * Every toast of the auth module. Copy follows the F-16 PRD toast catalogue (section 5.7): plain sentences, no
 * exclamation marks. Form errors stay inline next to the field (they are announced there); a toast confirms an
 * outcome the screen would otherwise leave silent.
 */
import { toast, toastApiError } from '@artha/design-system'

export const notify = {
  signedIn: () => toast.success('Signed in.', { id: 'auth-session' }),
  signedOut: () => toast.info('Signed out. See you soon.', { id: 'auth-session' }),
  signedUp: () => toast.success('Account created. Welcome to ArthaCommerce.', { id: 'auth-session' }),
  confirmationSent: (email: string) => toast.success(`Confirmation email sent to ${email}.`, { id: 'auth-email' }),
  codeSent: (email: string) => toast.success(`Sign-in code sent to ${email}.`, { id: 'auth-email' }),
  codeResent: () => toast.success('We sent a new code.', { id: 'auth-email' }),
  resetRequested: () => toast.success('Reset link requested. Check your inbox.', { id: 'auth-email' }),
  passwordUpdated: () => toast.success('Password updated.', { id: 'auth-password' }),
  emailChangeRequested: (email: string) =>
    toast.success(`Confirmation sent to ${email}. Your sign-in email changes once you confirm.`, {
      id: 'auth-email',
    }),
  failed: (error: unknown, fallback = 'Something went wrong. Please try again.') =>
    toastApiError(error, fallback, { id: 'auth-error' }),
}
