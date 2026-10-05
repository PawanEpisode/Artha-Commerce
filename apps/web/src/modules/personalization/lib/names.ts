/**
 * Name rules, mirrored from apps/api/modules/profiles/domain/names.py and checked against the same fixtures
 * (`names_cases.json`). The server is the authority; this gives the field an answer before the request.
 */
export const NAME_MIN = 1
export const NAME_MAX = 60

// Embedding, override and isolate controls plus line and paragraph separators (they can reorder text in a header).
const FORBIDDEN = new Set<number>([...range(0x202a, 0x202e), ...range(0x2066, 0x2069), 0x2028, 0x2029, 0x200e, 0x200f])

function range(from: number, to: number): number[] {
  return Array.from({ length: to - from + 1 }, (_, i) => from + i)
}

/** Control characters other than tab, newline, carriage return (those collapse into spaces). */
const isControl = (code: number) =>
  (code <= 0x1f && ![0x09, 0x0a, 0x0d].includes(code)) || (code >= 0x7f && code <= 0x9f)

const hasForbidden = (text: string) =>
  Array.from(text).some((ch) => FORBIDDEN.has(ch.codePointAt(0) ?? 0) || isControl(ch.codePointAt(0) ?? 0))

export type NameCheck = { ok: true; name: string } | { ok: false; message: string }

export function checkName(raw: string): NameCheck {
  const text = (raw ?? '').normalize('NFC')
  if (hasForbidden(text)) {
    return { ok: false, message: 'Use letters, numbers and normal punctuation only.' }
  }
  const name = text.replace(/\s+/gu, ' ').trim()
  if (name.length < NAME_MIN) return { ok: false, message: 'Enter your name.' }
  if (Array.from(name).length > NAME_MAX) return { ok: false, message: `Use ${NAME_MAX} characters or fewer.` }
  return { ok: true, name }
}

export const firstNameOf = (fullName: string) => fullName.split(' ', 1)[0] ?? ''
