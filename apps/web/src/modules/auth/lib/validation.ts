/** Client-side validation for auth forms. Supabase enforces the real rules (see supabase/config.toml); this gives instant feedback. Each returns an error message or undefined. */

export const PASSWORD_MIN_LENGTH = 8
/** bcrypt only uses the first 72 bytes. */
export const PASSWORD_MAX_LENGTH = 72
export const OTP_LENGTH = 6

const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/

export const PASSWORD_HINT = `At least ${PASSWORD_MIN_LENGTH} characters, with a letter and a number.`

export function normalizeEmail(raw: string): string {
  return raw.trim().toLowerCase()
}

export function validateEmail(raw: string): string | undefined {
  const email = normalizeEmail(raw)
  if (!email) return 'Enter your email address.'
  if (!EMAIL_PATTERN.test(email)) return 'Enter a valid email address.'
  return undefined
}

export function validatePassword(raw: string): string | undefined {
  if (!raw) return 'Enter a password.'
  if (raw.length < PASSWORD_MIN_LENGTH) return `Use at least ${PASSWORD_MIN_LENGTH} characters.`
  if (raw.length > PASSWORD_MAX_LENGTH) return `Use at most ${PASSWORD_MAX_LENGTH} characters.`
  if (!/[A-Za-z]/.test(raw) || !/\d/.test(raw)) return 'Include at least one letter and one number.'
  return undefined
}

export function validatePasswordMatch(password: string, confirm: string): string | undefined {
  return password === confirm ? undefined : 'The two passwords do not match.'
}

/** Strips spaces and dashes people add when typing codes (`123 456`). */
export function normalizeOtp(raw: string): string {
  return raw.replace(/[\s-]/g, '')
}

export function validateOtp(raw: string): string | undefined {
  const code = normalizeOtp(raw)
  if (!code) return 'Enter the code from your email.'
  if (!new RegExp(`^\\d{${OTP_LENGTH}}$`).test(code)) return `The code has ${OTP_LENGTH} digits.`
  return undefined
}
