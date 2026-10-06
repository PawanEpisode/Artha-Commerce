import { describe, expect, it } from 'vitest'

import {
  announceChange,
  bellCountLabel,
  flattenInbox,
  followableLink,
  formatSent,
  isModifiedClick,
  markReadInPages,
  secondsSince,
  unreadPhrase,
} from './inbox'
import type { InboxItem, InboxPage } from './schemas'

const item = (id: string, read = false, over: Partial<InboxItem> = {}): InboxItem => ({
  id,
  category: 'timer',
  category_label: 'Timer alerts',
  title: `Item ${id}`,
  body: 'Body',
  deep_link: '/app/focus',
  read,
  created_at: '2026-10-05T04:30:00Z',
  ...over,
})
const page = (results: InboxItem[], unread: number, next: string | null = null): InboxPage => ({
  results,
  next_cursor: next,
  unread_count: unread,
})

describe('the bell text', () => {
  it.each([
    [0, ''],
    [-2, ''],
    [1, '1'],
    [99, '99'],
    [100, '99+'],
    [4000, '99+'],
  ])('shows %i as "%s"', (count, label) => expect(bellCountLabel(count)).toBe(label))

  it.each([
    [0, 'No unread notifications'],
    [1, '1 unread notification'],
    [5, '5 unread notifications'],
  ])('says %i aloud as "%s"', (count, phrase) => expect(unreadPhrase(count)).toBe(phrase))
})

describe('announceChange', () => {
  it('is silent for the first answer and for an unchanged count', () => {
    expect(announceChange(null, 3)).toBeNull()
    expect(announceChange(3, 3)).toBeNull()
  })
  it('announces a rise and a fall, including back to zero', () => {
    expect(announceChange(3, 4)).toBe('4 unread notifications')
    expect(announceChange(1, 0)).toBe('No unread notifications')
    expect(announceChange(0, 1)).toBe('1 unread notification')
  })
})

describe('time', () => {
  const sent = '2026-10-05T04:30:00Z'
  const at = (ms: number) => Date.parse(sent) + ms
  it('counts whole seconds and never goes negative', () => {
    expect(secondsSince(sent, at(42_400))).toBe(42)
    expect(secondsSince(sent, at(-5_000))).toBe(0)
    expect(secondsSince('nonsense', at(1000))).toBe(0)
  })
  it.each([
    [10_000, 'just now'],
    [5 * 60_000, '5 min ago'],
    [3 * 3_600_000, '3 h ago'],
    [30 * 3_600_000, 'yesterday'],
    [4 * 86_400_000, '4 days ago'],
  ])('writes %i ms as "%s"', (ms, text) => expect(formatSent(sent, at(ms))).toBe(text))
  it('writes a date after a week and nothing for a bad value', () => {
    expect(formatSent(sent, at(9 * 86_400_000))).toMatch(/5 Oct/)
    expect(formatSent('nonsense', 0)).toBe('')
  })
})

describe('followableLink', () => {
  it('keeps an allow-listed relative path, query included', () => {
    expect(followableLink({ deep_link: '/app/focus?x=1' })).toBe('/app/focus?x=1')
    expect(followableLink({ deep_link: '/app' })).toBe('/app')
  })
  it.each(['https://evil.example', '//evil.example', '/login', '/app/../etc', '/app%2f..', 'javascript:alert(1)', ''])(
    'refuses %s',
    (deep_link) => expect(followableLink({ deep_link })).toBeNull(),
  )
})

describe('isModifiedClick', () => {
  const plain = { button: 0, metaKey: false, ctrlKey: false, shiftKey: false, altKey: false }
  it('leaves only a plain left click to the app', () => {
    expect(isModifiedClick(plain)).toBe(false)
    expect(isModifiedClick({ ...plain, ctrlKey: true })).toBe(true)
    expect(isModifiedClick({ ...plain, metaKey: true })).toBe(true)
    expect(isModifiedClick({ ...plain, shiftKey: true })).toBe(true)
    expect(isModifiedClick({ ...plain, altKey: true })).toBe(true)
    expect(isModifiedClick({ ...plain, button: 1 })).toBe(true)
  })
})

describe('markReadInPages', () => {
  const data = () => ({
    pages: [page([item('a'), item('b', true)], 3, 'c1'), page([item('c'), item('d')], 3)],
    pageParams: [null, 'c1'],
  })

  it('marks the listed items on any page and lowers the count by what changed', () => {
    const next = markReadInPages(data(), { ids: ['a', 'd', 'b'] })
    expect(next.pages.flatMap((p) => p.results).map((i) => i.read)).toEqual([true, true, false, true])
    expect(next.pages.map((p) => p.unread_count)).toEqual([1, 1])
  })

  it('marks everything and zeroes the count', () => {
    const next = markReadInPages(data(), { all: true })
    expect(next.pages.flatMap((p) => p.results).every((i) => i.read)).toBe(true)
    expect(next.pages.map((p) => p.unread_count)).toEqual([0, 0])
  })

  it('does not mutate the cache it was given, and keeps the page params', () => {
    const before = data()
    const next = markReadInPages(before, { ids: ['a'] })
    expect(before.pages[0]?.results[0]?.read).toBe(false)
    expect(next.pageParams).toEqual([null, 'c1'])
  })

  it('never goes below zero', () => {
    const next = markReadInPages({ pages: [page([item('a')], 0)], pageParams: [null] }, { ids: ['a'] })
    expect(next.pages[0]?.unread_count).toBe(0)
  })
})

describe('flattenInbox', () => {
  it('joins the pages in order and drops an item that shows twice', () => {
    const data = {
      pages: [page([item('a'), item('b')], 2, 'x'), page([item('b'), item('c')], 2)],
      pageParams: [null, 'x'],
    }
    expect(flattenInbox(data).map((i) => i.id)).toEqual(['a', 'b', 'c'])
  })
  it('is empty before the first answer', () => expect(flattenInbox(undefined)).toEqual([]))
})
