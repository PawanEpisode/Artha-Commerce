/**
 * Email clients do not support CSS variables or OKLCH, so email uses fixed hex values.
 * They are the sRGB equivalents of the design tokens in packages/design-system/src/styles.css
 * (Reading theme for the page, Dark theme for dark-mode clients). Re-derive them if the tokens change.
 */
export const brand = {
  name: 'ArthaCommerce',
  tagline: 'Exam preparation for CA, CS and CMA',
  light: {
    page: '#f7f0dd',
    card: '#fcf6e9',
    text: '#2b2018',
    muted: '#605245',
    border: '#ddd3bf',
    primary: '#3643ae',
    onPrimary: '#fbf8f1',
    codeBg: '#efe5d0',
  },
  dark: {
    page: '#090d18',
    card: '#101524',
    text: '#f3f2ec',
    muted: '#9ea5b2',
    border: '#272d3d',
    primary: '#738cff',
    onPrimary: '#090d18',
    codeBg: '#1a2133',
  },
} as const

/** Matches `otp_expiry` in supabase/config.toml (seconds). Keep the copy and the setting in sync. */
export const OTP_EXPIRY_MINUTES = 60
