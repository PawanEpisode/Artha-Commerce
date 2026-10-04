import type { EmailOtpType } from '@supabase/supabase-js'

import { getSupabase } from '~/lib/supabase'

import { type AuthErrorLike, friendlyAuthError, isReauthRequired } from './errors'
import { callbackUrl } from './redirects'
import { normalizeEmail, normalizeOtp } from './validation'

/**
 * Thin wrappers over supabase-js auth calls. Every function returns `{ error?: string }` with a student-friendly message,
 * so containers never see raw SDK errors. No React in here: easy to test and reuse.
 */
export interface AuthResult {
  error?: string
  /** Set when the server asks the student to confirm with an emailed code before continuing. */
  needsReauth?: boolean
}

const NOT_CONFIGURED = 'Sign-in is not configured yet. Add the Supabase env vars.'

async function run(call: (s: NonNullable<ReturnType<typeof getSupabase>>) => Promise<{ error: AuthErrorLike | null }>) {
  const supabase = getSupabase()
  if (!supabase) return { error: NOT_CONFIGURED }
  try {
    const { error } = await call(supabase)
    if (!error) return {}
    return { error: friendlyAuthError(error), needsReauth: isReauthRequired(error) || undefined }
  } catch {
    return { error: friendlyAuthError(null) }
  }
}

const origin = () => window.location.origin

/** Sign in with a one-time link and 6 digit code (works for new and existing accounts). */
export const sendEmailCode = (email: string) =>
  run((s) =>
    s.auth.signInWithOtp({ email: normalizeEmail(email), options: { emailRedirectTo: callbackUrl(origin()) } }),
  )

export const verifyEmailCode = (
  email: string,
  code: string,
  type: Extract<EmailOtpType, 'email' | 'signup'> = 'email',
) => run((s) => s.auth.verifyOtp({ email: normalizeEmail(email), token: normalizeOtp(code), type }))

export const signInWithPassword = (email: string, password: string) =>
  run((s) => s.auth.signInWithPassword({ email: normalizeEmail(email), password }))

/** Creates the account. With "Confirm email" on, the student must then confirm by link or code. */
export const signUpWithPassword = (email: string, password: string) =>
  run((s) =>
    s.auth.signUp({ email: normalizeEmail(email), password, options: { emailRedirectTo: callbackUrl(origin()) } }),
  )

/** Re-sends the signup confirmation (link and code). */
export const resendSignupEmail = (email: string) =>
  run((s) =>
    s.auth.resend({
      type: 'signup',
      email: normalizeEmail(email),
      options: { emailRedirectTo: callbackUrl(origin()) },
    }),
  )

export const requestPasswordReset = (email: string) =>
  run((s) => s.auth.resetPasswordForEmail(normalizeEmail(email), { redirectTo: `${origin()}/auth/reset-password` }))

/** Verifies a token_hash from an email link (used by /auth/confirm). */
export const confirmTokenHash = (tokenHash: string, type: EmailOtpType) =>
  run((s) => s.auth.verifyOtp({ token_hash: tokenHash, type }))

/** Sends a verification code to the signed-in student's email (Reauthentication template). */
export const sendReauthCode = () => run((s) => s.auth.reauthenticate())

/** Sets or changes the password. If the server wants a recent sign-in, returns `needsReauth` and the caller asks for a code. */
export const updatePassword = (password: string, nonce?: string) =>
  run((s) => s.auth.updateUser({ password, ...(nonce ? { nonce: normalizeOtp(nonce) } : {}) }))

/** Starts an email change: Supabase emails a confirmation to the new address (and the old one when secure change is on). */
export const requestEmailChange = (newEmail: string) =>
  run((s) =>
    s.auth.updateUser({ email: normalizeEmail(newEmail) }, { emailRedirectTo: callbackUrl(origin(), '/app/account') }),
  )
