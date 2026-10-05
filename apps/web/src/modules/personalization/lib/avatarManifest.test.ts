import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'

import { AVATAR_PRESET_KEYS } from '@artha/design-system'
import { describe, expect, it } from 'vitest'

describe('avatar preset manifest', () => {
  it('has the same 24 keys as the API catalogue', () => {
    const py = readFileSync(
      fileURLToPath(new URL('../../../../../api/modules/profiles/domain/avatars.py', import.meta.url)),
      'utf8',
    )
    const count = Number(/PRESET_COUNT = (\d+)/.exec(py)?.[1])
    const expected = Array.from({ length: count }, (_, i) => `p${String(i + 1).padStart(2, '0')}`)
    expect([...AVATAR_PRESET_KEYS]).toEqual(expected)
    expect(AVATAR_PRESET_KEYS).toHaveLength(24)
  })
})
