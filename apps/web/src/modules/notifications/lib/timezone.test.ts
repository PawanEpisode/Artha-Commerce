import { describe, expect, it } from 'vitest'

import { browserTimeZone, isValidTimeZone, normalizeTimeZone, proposeTimeZone, timeZoneOptions } from './timezone'

describe('time zone helpers', () => {
  it('checks IANA names with Intl', () => {
    expect(isValidTimeZone('Asia/Kolkata')).toBe(true)
    expect(isValidTimeZone('Mars/Olympus')).toBe(false)
    expect(isValidTimeZone('')).toBe(false)
  })

  it('maps an old name to the one the API stores', () => {
    expect(normalizeTimeZone('Asia/Calcutta')).toBe('Asia/Kolkata')
    expect(normalizeTimeZone('Europe/London')).toBe('Europe/London')
  })

  it('reads a usable zone from the browser', () => {
    const zone = browserTimeZone()
    expect(zone === null || isValidTimeZone(zone)).toBe(true)
  })

  it('proposes the browser zone only when it really differs', () => {
    expect(proposeTimeZone('Asia/Kolkata', 'Asia/Dubai')).toBe('Asia/Dubai')
    expect(proposeTimeZone('Asia/Kolkata', 'Asia/Kolkata')).toBeNull()
    expect(proposeTimeZone('Asia/Kolkata', 'Asia/Calcutta')).toBeNull()
    expect(proposeTimeZone('Asia/Kolkata', null)).toBeNull()
  })

  it('lists zones, always including the saved and the browser zone, without duplicates', () => {
    const options = timeZoneOptions('Pacific/Chatham', 'Asia/Dubai')
    const values = options.map((o) => o.value)
    expect(values).toContain('Pacific/Chatham')
    expect(values).toContain('Asia/Dubai')
    expect(values).toContain('Asia/Kolkata')
    expect(new Set(values).size).toBe(values.length)
    expect(options.find((o) => o.value === 'Asia/Kolkata')?.label).toBe('Asia / Kolkata')
    expect(options.find((o) => o.value === 'America/Argentina/Buenos_Aires')?.label ?? 'Buenos Aires').toContain(
      'Buenos Aires',
    )
  })

  it('keeps a saved legacy name selectable under its modern one', () => {
    const values = timeZoneOptions('Asia/Calcutta', null).map((o) => o.value)
    expect(values).toContain('Asia/Kolkata')
    expect(values).not.toContain('Asia/Calcutta')
  })
})
