import { existsSync, readdirSync, readFileSync, statSync } from 'node:fs'
import { join } from 'node:path'
import { fileURLToPath } from 'node:url'

import { describe, expect, it } from 'vitest'

import { isAllowedDeepLink } from './deeplink'

const read = (relative: string) => readFileSync(fileURLToPath(new URL(relative, import.meta.url)))
const json = <T>(relative: string): T => JSON.parse(read(relative).toString('utf8')) as T

interface Manifest {
  id: string
  scope: string
  start_url: string
  display: string
  icons: { src: string; sizes: string; type: string; purpose?: string }[]
  shortcuts?: { name: string; url: string }[]
}
interface VercelConfig {
  headers?: { source: string; headers: { key: string; value: string }[] }[]
}

const manifest = json<Manifest>('../../public/manifest.webmanifest')
const vercel = json<VercelConfig>('../../vercel.json')

/** Width and height from a PNG's IHDR chunk. */
function pngSize(file: Buffer): { width: number; height: number } {
  expect(file.subarray(1, 4).toString('ascii')).toBe('PNG')
  return { width: file.readUInt32BE(16), height: file.readUInt32BE(20) }
}

describe('web manifest (FR-N1)', () => {
  it('has a stable id, a scope and a standalone display', () => {
    expect(manifest.id).toBe('/')
    expect(manifest.scope).toBe('/')
    expect(manifest.display).toBe('standalone')
    expect(manifest.start_url.startsWith('/')).toBe(true)
  })

  it('lists 192, 512 and maskable 512 icons that exist at the stated size', () => {
    const purposes = manifest.icons.map((i) => `${i.sizes}:${i.purpose ?? 'any'}`)
    expect(purposes).toEqual(expect.arrayContaining(['192x192:any', '512x512:any', '512x512:maskable']))
    for (const icon of manifest.icons) {
      const { width, height } = pngSize(read(`../../public${icon.src}`) as Buffer)
      expect(`${width}x${height}`).toBe(icon.sizes)
      expect(icon.type).toBe('image/png')
    }
  })

  it('opens the focus timer from its shortcut, a page a notification may also open', () => {
    const urls = (manifest.shortcuts ?? []).map((s) => s.url)
    expect(urls).toContain('/app/focus')
    for (const url of urls) expect(isAllowedDeepLink(url)).toBe(true)
  })

  it('uses the 192 px icon for notifications (the file the worker names)', () => {
    expect(manifest.icons.some((i) => i.src === '/icon-192.png')).toBe(true)
  })
})

describe('vercel.json headers (FR-N30)', () => {
  const rule = vercel.headers?.find((h) => h.source === '/sw.js')
  const header = (key: string) => rule?.headers.find((h) => h.key.toLowerCase() === key.toLowerCase())?.value

  it('serves the worker uncached, so a deploy is picked up on the next visit', () => {
    expect(rule).toBeDefined()
    expect(header('Cache-Control')).toMatch(/no-cache/)
    expect(header('Cache-Control')).toMatch(/must-revalidate/)
  })

  it('lets the worker control the whole site', () => {
    expect(header('Service-Worker-Allowed')).toBe('/')
  })
})

/** True when a Permissions-Policy value switches `feature` off (empty allow-list) for the page. */
function disables(policy: string, feature: string): boolean {
  return policy
    .split(',')
    .map((part) => part.trim())
    .some((part) => new RegExp(`^${feature}\\s*=\\s*\\(\\s*\\)$`).test(part) || part === `${feature}=none`)
}

describe('no policy switches notifications or the wake lock off (PRD 11, security row)', () => {
  const FEATURES = ['notifications', 'push', 'screen-wake-lock']
  const policyHeaders = (vercel.headers ?? []).flatMap((rule) =>
    rule.headers
      .filter((h) => ['permissions-policy', 'feature-policy'].includes(h.key.toLowerCase()))
      .map((h) => ({ source: rule.source, value: h.value })),
  )

  it.each(FEATURES)('does not disable %s in any Permissions-Policy header of vercel.json', (feature) => {
    for (const { source, value } of policyHeaders) {
      expect(disables(value, feature), `${source} disables ${feature}`).toBe(false)
    }
  })

  it('would notice a policy that does (the check itself works)', () => {
    expect(disables('camera=(), notifications=()', 'notifications')).toBe(true)
    expect(disables('screen-wake-lock=( )', 'screen-wake-lock')).toBe(true)
    expect(disables('notifications=none', 'notifications')).toBe(true)
    expect(disables('notifications=(self), camera=()', 'notifications')).toBe(false)
    expect(disables('camera=()', 'notifications')).toBe(false)
  })
})

describe('FR-K7: nothing else sets a Permissions-Policy for the app routes', () => {
  const webRoot = fileURLToPath(new URL('../../', import.meta.url))
  const sourceFiles = (dir: string): string[] =>
    readdirSync(dir).flatMap((name) => {
      const path = join(dir, name)
      if (statSync(path).isDirectory()) return sourceFiles(path)
      return /\.(ts|tsx)$/.test(name) && !/\.test\.tsx?$/.test(name) ? [path] : []
    })

  it('sends no Permissions-Policy or Feature-Policy header from application code', () => {
    const offenders = sourceFiles(join(webRoot, 'src')).filter((file) =>
      /permissions-policy|feature-policy/i.test(readFileSync(file, 'utf8')),
    )
    expect(offenders).toEqual([])
  })

  it('has no static _headers file that could set one', () => {
    expect(existsSync(join(webRoot, 'public', '_headers'))).toBe(false)
  })

  it('has no header rule for /app that switches the wake lock or notifications off', () => {
    const appRules = (vercel.headers ?? []).filter((rule) => /^\/(app|\(\.\*\)|:path\*|\.\*)/.test(rule.source))
    for (const rule of appRules) {
      for (const h of rule.headers.filter((x) => /permissions-policy|feature-policy/i.test(x.key))) {
        expect(disables(h.value, 'screen-wake-lock')).toBe(false)
        expect(disables(h.value, 'notifications')).toBe(false)
      }
    }
  })
})
