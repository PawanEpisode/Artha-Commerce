import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'

import { describe, expect, it } from 'vitest'

import {
  DEEP_LINK_EXACT_ROUTES,
  DEEP_LINK_MAX_LENGTH,
  DEEP_LINK_PREFIXES,
  DEFAULT_DEEP_LINK,
  isAllowedDeepLink,
  resolveDeepLink,
  safeDeepLink,
} from './deeplink'

const ORIGIN = 'https://app.example.test'

describe('isAllowedDeepLink', () => {
  it.each([
    '/app',
    '/app/',
    '/app/focus',
    '/app/focus?n=abc123',
    '/app/focus/history',
    '/app/tracker/day/2026-10-06',
    '/app/syllabus/fin-acc/ch-3#top',
    '/app/notifications',
    '/app/settings/notifications?n=1',
  ])('accepts %s', (path) => {
    expect(isAllowedDeepLink(path)).toBe(true)
  })

  it.each([
    ['protocol-relative', '//evil.example/app/focus'],
    ['absolute https', 'https://evil.example/app/focus'],
    ['absolute http', 'http://localhost:3000/app'],
    ['javascript scheme', 'javascript:alert(1)'],
    ['data scheme', 'data:text/html,hi'],
    ['no leading slash', 'app/focus'],
    ['backslash host trick', '/\\evil.example'],
    ['backslash inside', '/app/focus\\..\\x'],
    ['slash backslash', '/\\/evil.example'],
    ['dot segments', '/app/focus/../../admin'],
    ['single dot segment', '/app/./focus'],
    ['encoded slash', '/app/focus%2f..%2fadmin'],
    ['encoded dot', '/app/%2e%2e/admin'],
    ['encoded backslash', '/app%5cfocus'],
    ['newline', '/app/focus\n/evil'],
    ['tab before host', '/\t/evil.example'],
    ['null byte', '/app/focus\u0000'],
    ['not on the allow-list', '/admin'],
    ['settings but not notifications', '/app/settings/focus'],
    ['prefix without a slash boundary', '/app/focusing'],
    ['root', '/'],
    ['empty', ''],
    ['too long', `/app/focus?${'a'.repeat(DEEP_LINK_MAX_LENGTH)}`],
  ])('rejects %s', (_label, path) => {
    expect(isAllowedDeepLink(path)).toBe(false)
  })

  it.each([undefined, null, 42, {}, ['/app']])('rejects a non-string (%s)', (value) => {
    expect(isAllowedDeepLink(value)).toBe(false)
  })
})

describe('safeDeepLink and resolveDeepLink', () => {
  it('keeps an allowed link exactly as sent', () => {
    expect(safeDeepLink('/app/focus?n=abc')).toBe('/app/focus?n=abc')
  })

  it('falls back to the app home for anything refused', () => {
    expect(safeDeepLink('//evil.example')).toBe(DEFAULT_DEEP_LINK)
    expect(safeDeepLink(undefined)).toBe(DEFAULT_DEEP_LINK)
  })

  it('resolves against the worker origin and never leaves it', () => {
    expect(resolveDeepLink('/app/focus?n=7', ORIGIN)).toBe(`${ORIGIN}/app/focus?n=7`)
    expect(resolveDeepLink('//evil.example/x', ORIGIN)).toBe(`${ORIGIN}/app`)
    expect(resolveDeepLink('https://evil.example/app', ORIGIN)).toBe(`${ORIGIN}/app`)
    expect(new URL(resolveDeepLink('/\\evil.example', ORIGIN)).origin).toBe(ORIGIN)
  })
})

describe('API parity', () => {
  const py = readFileSync(
    fileURLToPath(new URL('../../../api/modules/notifications/domain/deeplinks.py', import.meta.url)),
    'utf8',
  )
  const pythonStrings = (block: string | undefined) => [...(block ?? '').matchAll(/"([^"]+)"/g)].map((m) => m[1])

  it('uses the same exact routes as the API allow-list', () => {
    expect(DEEP_LINK_EXACT_ROUTES).toEqual(pythonStrings(/EXACT_ROUTES = frozenset\(\{([^}]*)\}\)/.exec(py)?.[1]))
  })

  it('uses the same route prefixes as the API allow-list', () => {
    expect(DEEP_LINK_PREFIXES).toEqual(pythonStrings(/ALLOWED_PREFIXES = \(([^)]*)\)/.exec(py)?.[1]))
  })

  it('uses the same length limit as the API', () => {
    expect(DEEP_LINK_MAX_LENGTH).toBe(Number(/MAX_LENGTH = (\d+)/.exec(py)?.[1]))
  })
})
