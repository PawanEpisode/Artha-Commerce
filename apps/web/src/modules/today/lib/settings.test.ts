import { describe, expect, it } from 'vitest'

import { changedKeys, DEFAULT_SETTINGS, focusFromValue, focusValue, kindLabel, listedKinds } from './settings'
import type { TodaySettings } from './types'

const saved: TodaySettings = {
  minutes_per_day: 60,
  focus_papers: null,
  disabled_kinds: ['next_chapter'],
  show_tomorrow: true,
  celebrate: false,
  lite_mode: 'auto',
}

describe('today settings helpers', () => {
  it('names only the settings that changed', () => {
    expect(changedKeys(saved, { ...saved, minutes_per_day: 90, celebrate: false })).toEqual(['minutes_per_day'])
    expect(changedKeys(saved, { disabled_kinds: ['next_chapter'] })).toEqual([])
    expect(changedKeys(saved, { disabled_kinds: [] })).toEqual(['disabled_kinds'])
  })
  it('the defaults are automatic with nothing hidden', () => {
    expect(DEFAULT_SETTINGS).toEqual({
      minutes_per_day: null,
      focus_papers: null,
      disabled_kinds: [],
      show_tomorrow: true,
      celebrate: true,
      lite_mode: 'auto',
    })
  })
  it('words known kinds and humanises unknown ones', () => {
    expect(kindLabel('recall_cards')).toBe('Flashcards that are due')
    expect(kindLabel('mock_test_set')).toBe('Mock test set')
  })
  it('lists a hidden kind it does not know so it can be switched back on', () => {
    expect(listedKinds(['mock_test_set', 'recall_cards']).slice(-1)).toEqual(['mock_test_set'])
  })
  it('maps focus papers to and from the control', () => {
    expect(focusValue(null)).toBe('auto')
    expect(focusValue(3)).toBe('3')
    expect(focusFromValue('auto')).toBeNull()
    expect(focusFromValue('2')).toBe(2)
  })
})
