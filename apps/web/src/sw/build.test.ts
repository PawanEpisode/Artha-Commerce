import { build } from 'esbuild'
import { describe, expect, it } from 'vitest'

import { swBuildOptions, swVersionFrom } from '../../scripts/sw-build-options.mjs'

/** Builds the worker in memory, the way `scripts/build-sw.mjs` does, and checks what ships. */
async function bundle(options: Parameters<typeof swBuildOptions>[0] = {}) {
  const result = await build({ ...swBuildOptions({ ...options, write: false }), absWorkingDir: process.cwd() })
  expect(result.errors).toEqual([])
  expect(result.outputFiles).toHaveLength(1)
  return result.outputFiles?.[0]?.text ?? ''
}

describe('service worker bundle (FR-N30)', () => {
  it('is one self-contained script with the version baked in', async () => {
    const code = await bundle({ version: 'abc1234' })
    expect(code).toContain('abc1234')
    expect(code).not.toMatch(/\bimport\s*\(|\bimport\s+["'{*]|\brequire\(/)
  })

  it('listens for the events it needs and no others', async () => {
    const code = await bundle()
    for (const event of ['install', 'activate', 'push', 'notificationclick', 'pushsubscriptionchange']) {
      expect(code).toContain(`"${event}"`)
    }
    expect(code).toContain('skipWaiting')
    expect(code).toContain('claim')
  })

  it('contains no page caching: no fetch handler and no Cache API', async () => {
    const code = await bundle()
    expect(code).not.toContain('"fetch"')
    expect(code).not.toMatch(/\bcaches\b/)
    expect(code).not.toContain('CacheStorage')
  })

  it('bakes in the API origin that notification buttons post to', async () => {
    expect(await bundle({ apiBaseUrl: 'https://api.example.test' })).toContain('https://api.example.test')
  })

  it('falls back to the dev version when none is given', async () => {
    expect(await bundle({ version: 'dev' })).toContain('"dev"')
  })
})

describe('swVersionFrom', () => {
  it('uses the first seven characters of the Vercel commit, else dev', () => {
    expect(swVersionFrom({ VERCEL_GIT_COMMIT_SHA: '0123456789abcdef' })).toBe('0123456')
    expect(swVersionFrom({})).toBe('dev')
    expect(swVersionFrom({ VERCEL_GIT_COMMIT_SHA: '' })).toBe('dev')
  })
})
