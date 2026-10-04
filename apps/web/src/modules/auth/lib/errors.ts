/** Maps Supabase Auth errors to messages a student can act on. Unknown errors get a generic message (never raw server text). */
export interface AuthErrorLike {
  code?: string
  message?: string
  status?: number
}

const MESSAGES: Record<string, string> = {
  invalid_credentials: 'That email and password do not match. Try again, or reset your password.',
  email_not_confirmed: 'Confirm your email first. Check your inbox for the link or code.',
  user_already_exists: 'An account with this email already exists. Sign in instead.',
  email_exists: 'That email is already used by another account.',
  over_email_send_rate_limit: 'Too many emails sent. Please wait a few minutes and try again.',
  over_request_rate_limit: 'Too many attempts. Please wait a minute and try again.',
  otp_expired: 'That code or link has expired. Request a new one.',
  otp_disabled: 'Email sign-in is not enabled yet.',
  weak_password: 'Choose a stronger password: at least 8 characters with a letter and a number.',
  same_password: 'Your new password must be different from the old one.',
  reauthentication_needed: 'For your security, confirm it is you with the code we email you.',
  reauthentication_not_valid: 'That code is not valid. Check the latest email and try again.',
  validation_failed: 'Check the details you entered and try again.',
  signup_disabled: 'New sign-ups are paused right now.',
  email_address_invalid: 'That email address is not accepted. Use a different one.',
  session_not_found: 'Your session has ended. Sign in again.',
  user_not_found: 'Your session has ended. Sign in again.',
}

export const GENERIC_AUTH_ERROR = 'Something went wrong. Please try again.'

export function friendlyAuthError(error: AuthErrorLike | null | undefined): string {
  if (!error) return GENERIC_AUTH_ERROR
  if (error.code && MESSAGES[error.code]) return MESSAGES[error.code]
  if (error.status === 429) return MESSAGES.over_request_rate_limit
  if (error.message && /expired|invalid/i.test(error.message) && /token|otp|link|code/i.test(error.message)) {
    return MESSAGES.otp_expired
  }
  return GENERIC_AUTH_ERROR
}

export function isReauthRequired(error: AuthErrorLike | null | undefined): boolean {
  return error?.code === 'reauthentication_needed'
}
