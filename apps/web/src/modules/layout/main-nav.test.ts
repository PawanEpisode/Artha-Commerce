import { describe, expect, it } from 'vitest'

import { mainNav } from './main-nav'

describe('mainNav', () => {
  it('offers Features and Courses to a guest', () => {
    expect(mainNav(false).map((item) => item.label)).toEqual(['Features', 'Courses'])
  })

  it('drops Courses once the student is signed in', () => {
    expect(mainNav(true)).toEqual([{ to: '/features', label: 'Features' }])
  })
})
