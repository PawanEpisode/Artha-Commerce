import { describe, expect, it } from 'vitest'

import {
  normalizeEmail,
  normalizeOtp,
  validateEmail,
  validateOtp,
  validatePassword,
  validatePasswordMatch,
} from './validation'

describe('email', () => {
  it('normalises case and spaces', () => expect(normalizeEmail('  Aarav@Example.COM ')).toBe('aarav@example.com'))
  it('accepts normal addresses', () => {
    for (const e of ['a@b.co', 'first.last+tag@sub.example.in']) expect(validateEmail(e)).toBeUndefined()
  })
  it('rejects empty and malformed', () => {
    for (const e of ['', ' ', 'abc', 'a@b', 'a@@b.com', 'a b@c.com']) expect(validateEmail(e)).toBeTruthy()
  })
})

describe('password', () => {
  it('requires length, a letter and a number', () => {
    expect(validatePassword('')).toBeTruthy()
    expect(validatePassword('short1')).toMatch(/at least 8/)
    expect(validatePassword('longlonglong')).toMatch(/letter and one number/)
    expect(validatePassword('12345678')).toMatch(/letter and one number/)
    expect(validatePassword('Study2027')).toBeUndefined()
  })
  it('caps length at 72', () => expect(validatePassword('a1'.repeat(40))).toMatch(/at most 72/))
  it('checks confirmation', () => {
    expect(validatePasswordMatch('a', 'a')).toBeUndefined()
    expect(validatePasswordMatch('a', 'b')).toBeTruthy()
  })
})

describe('otp', () => {
  it('ignores spaces and dashes', () => expect(normalizeOtp('123 456')).toBe('123456'))
  it('needs exactly 6 digits', () => {
    expect(validateOtp('123456')).toBeUndefined()
    expect(validateOtp('123-456')).toBeUndefined()
    expect(validateOtp('')).toBeTruthy()
    expect(validateOtp('12345')).toBeTruthy()
    expect(validateOtp('12345a')).toBeTruthy()
  })
})
