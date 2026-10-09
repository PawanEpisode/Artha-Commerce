import { describe, expect, it } from 'vitest'

import { callbackUrl, isConfirmType, postConfirmPath, safeNextPath } from './redirects'

describe('safeNextPath', () => {
  it('keeps same-site paths', () => {
    expect(safeNextPath('/app/account')).toBe('/app/account')
    expect(safeNextPath('/courses/ca?x=1')).toBe('/courses/ca?x=1')
  })
  it('blocks open redirects', () => {
    for (const bad of ['//evil.com', 'https://evil.com', 'javascript:alert(1)', '/\\evil.com', 'app', '', '/a\nb']) {
      expect(safeNextPath(bad)).toBe('/app')
    }
    expect(safeNextPath(undefined)).toBe('/app')
    expect(safeNextPath(42)).toBe('/app')
  })
  it('uses the given fallback', () => expect(safeNextPath('//x', '/login')).toBe('/login'))
  it('refuses sign-in pages, including a next that wraps another next', () => {
    for (const auth of [
      '/login',
      '/login?next=/app/notes/trash',
      '/signup',
      '/signup?x=1',
      '/auth',
      '/auth/callback',
      '/auth/confirm?token_hash=abc',
    ]) {
      expect(safeNextPath(auth)).toBe('/app')
    }
    expect(safeNextPath('/app/notes/trash')).toBe('/app/notes/trash')
  })
})

describe('postConfirmPath', () => {
  it('forces password setup after recovery and invite', () => {
    expect(postConfirmPath('recovery', '/app')).toBe('/auth/reset-password')
    expect(postConfirmPath('invite')).toBe('/auth/reset-password?mode=invite')
  })
  it('returns to account after an email change', () => expect(postConfirmPath('email_change')).toBe('/app/account'))
  it('honours a safe next for sign-in types, ignores unsafe', () => {
    expect(postConfirmPath('magiclink', '/app/syllabus')).toBe('/app/syllabus')
    expect(postConfirmPath('signup', '//evil.com')).toBe('/app')
  })
})

describe('helpers', () => {
  it('validates confirm types', () => {
    expect(isConfirmType('recovery')).toBe(true)
    expect(isConfirmType('hacker')).toBe(false)
  })
  it('builds the OAuth callback URL', () => {
    expect(callbackUrl('https://artha.example')).toBe('https://artha.example/auth/callback')
    expect(callbackUrl('https://artha.example', '/app/account')).toBe(
      'https://artha.example/auth/callback?next=%2Fapp%2Faccount',
    )
    expect(callbackUrl('https://artha.example', '//evil.com')).toBe('https://artha.example/auth/callback?next=%2Fapp')
  })
})
