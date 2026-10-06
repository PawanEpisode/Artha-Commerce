import { describe, expect, it } from 'vitest'

import { InvalidApplicationServerKey, sameKey, urlBase64ToUint8Array } from './applicationServerKey'

/** A well-formed key: 0x04 then 64 bytes, written the way `web-push generate-vapid-keys` prints it. */
const bytes = new Uint8Array(65).map((_, i) => (i === 0 ? 4 : (i * 7) % 256))
const KEY = btoa(String.fromCharCode(...bytes))
  .replace(/\+/g, '-')
  .replace(/\//g, '_')
  .replace(/=+$/, '')

describe('urlBase64ToUint8Array', () => {
  it('decodes URL-safe base64 without padding', () => {
    expect([...urlBase64ToUint8Array(KEY)]).toEqual([...bytes])
  })

  it('tolerates surrounding whitespace from an env file', () => {
    expect(urlBase64ToUint8Array(`  ${KEY}\n`)).toHaveLength(65)
  })

  it.each([
    ['empty', ''],
    ['not base64', 'not a key!'],
    ['too short', 'AAAA'],
    ['standard base64 characters', KEY.replace(/-/g, '+')],
    ['wrong first byte', btoa(String.fromCharCode(...new Uint8Array(65))).replace(/=+$/, '')],
  ])('rejects %s', (_label, key) => {
    expect(() => urlBase64ToUint8Array(key)).toThrow(InvalidApplicationServerKey)
  })
})

describe('sameKey', () => {
  it('compares bytes', () => {
    expect(sameKey(bytes.buffer.slice(0), bytes)).toBe(true)
    expect(sameKey(new Uint8Array(65).buffer, bytes)).toBe(false)
    expect(sameKey(new ArrayBuffer(3), bytes)).toBe(false)
    expect(sameKey(null, bytes)).toBe(false)
  })
})
