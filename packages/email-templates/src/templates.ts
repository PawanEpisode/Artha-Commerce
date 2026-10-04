import { brand } from './brand'
import { EXPIRY_NOTE, renderEmail } from './layout'

/**
 * Supabase Auth email types, in the same order as Dashboard > Authentication > Emails > Templates.
 * `key` is the name used in supabase/config.toml: [auth.email.template.<key>].
 *
 * Links go to our own /auth/confirm page with a token_hash (not Supabase's {{ .ConfirmationURL }}). The page verifies the
 * token in the browser, so email link scanners (Outlook Safe Links, corporate gateways) cannot use up the one-time token
 * by pre-fetching the link. A 6 digit code is included wherever it makes sign-in easier on a phone.
 */
export interface EmailTemplate {
  key: 'confirmation' | 'invite' | 'magic_link' | 'email_change' | 'recovery' | 'reauthentication'
  file: string
  subject: string
  html: string
  /** Supabase variables the template must contain (checked by tests). */
  requires: string[]
}

const confirmUrl = (type: string, next: string) =>
  `{{ .SiteURL }}/auth/confirm?token_hash={{ .TokenHash }}&type=${type}&next=${encodeURIComponent(next)}`

export const templates: EmailTemplate[] = [
  {
    key: 'confirmation',
    file: 'confirm-signup.html',
    subject: `Confirm your ${brand.name} account`,
    requires: ['{{ .TokenHash }}', '{{ .SiteURL }}', '{{ .Token }}'],
    html: renderEmail({
      preheader: 'Confirm your email to start preparing smarter.',
      heading: 'Confirm your email',
      body: [
        `Welcome to ${brand.name}. Confirm your email address to finish creating your account and start planning your preparation.`,
      ],
      button: { label: 'Confirm email', url: confirmUrl('signup', '/app') },
      code: { intro: 'Prefer to type it? Enter this code on the sign-in screen:' },
      note: EXPIRY_NOTE,
      reason: `You received this because this email address was used to sign up for ${brand.name}. If it was not you, ignore this email and no account will be created.`,
    }),
  },
  {
    key: 'invite',
    file: 'invite-user.html',
    subject: `You have been invited to ${brand.name}`,
    requires: ['{{ .TokenHash }}', '{{ .SiteURL }}'],
    html: renderEmail({
      preheader: `Accept your invitation to ${brand.name}.`,
      heading: 'You are invited',
      body: [
        `You have been invited to join ${brand.name}. Accept the invitation to set a password and open your workspace.`,
      ],
      button: { label: 'Accept invitation', url: confirmUrl('invite', '/auth/reset-password?mode=invite') },
      note: EXPIRY_NOTE,
      reason: `You received this because someone invited {{ .Email }} to ${brand.name}. If you were not expecting it, you can ignore this email.`,
    }),
  },
  {
    key: 'magic_link',
    file: 'magic-link.html',
    subject: `Your ${brand.name} sign-in link and code`,
    requires: ['{{ .TokenHash }}', '{{ .SiteURL }}', '{{ .Token }}'],
    html: renderEmail({
      preheader: 'Your one-time sign-in link and code.',
      heading: 'Sign in to your workspace',
      body: ['Use the button below to sign in. No password needed.'],
      button: { label: 'Sign in', url: confirmUrl('magiclink', '/app') },
      code: { intro: 'On another device? Enter this code instead:' },
      note: EXPIRY_NOTE,
      reason: `You received this because a sign-in to ${brand.name} was requested for {{ .Email }}. If it was not you, ignore this email: nobody can sign in without the link or code.`,
    }),
  },
  {
    key: 'email_change',
    file: 'change-email.html',
    subject: `Confirm your new ${brand.name} email address`,
    requires: ['{{ .ConfirmationURL }}', '{{ .NewEmail }}', '{{ .Email }}'],
    html: renderEmail({
      preheader: 'Confirm the change to your account email.',
      heading: 'Confirm your new email',
      body: [
        'We received a request to change the email on your account from <strong>{{ .Email }}</strong> to <strong>{{ .NewEmail }}</strong>.',
        'Confirm to complete the change. You will keep all your plan, notes and progress.',
      ],
      button: { label: 'Confirm new email', url: '{{ .ConfirmationURL }}' },
      note: 'If you did not ask for this, do not click the button and secure your account by resetting your password.',
      reason: `You received this because an email change was requested on your ${brand.name} account.`,
    }),
  },
  {
    key: 'recovery',
    file: 'reset-password.html',
    subject: `Reset your ${brand.name} password`,
    requires: ['{{ .TokenHash }}', '{{ .SiteURL }}'],
    html: renderEmail({
      preheader: 'Choose a new password for your account.',
      heading: 'Reset your password',
      body: ['We received a request to reset the password for your account. Choose a new one with the button below.'],
      button: { label: 'Choose a new password', url: confirmUrl('recovery', '/auth/reset-password') },
      note: EXPIRY_NOTE,
      reason: `You received this because a password reset was requested for {{ .Email }}. If it was not you, ignore this email: your password stays the same.`,
    }),
  },
  {
    key: 'reauthentication',
    file: 'reauthentication.html',
    subject: `Your ${brand.name} verification code`,
    requires: ['{{ .Token }}'],
    html: renderEmail({
      preheader: 'Your code to confirm a sensitive change.',
      heading: 'Confirm it is you',
      body: [`Enter this code in ${brand.name} to confirm a sensitive change, such as changing your password.`],
      code: { intro: 'Your verification code:' },
      note: EXPIRY_NOTE,
      reason: `You received this because a sensitive action was started on your ${brand.name} account. If it was not you, reset your password right away.`,
    }),
  },
]
