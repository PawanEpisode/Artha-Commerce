import { describe, expect, it } from 'vitest'

import { currentSection, isSettingsPath, settingsLabel } from './app-nav'
import { STUDY_LINKS } from './workspace-nav'

describe('currentSection', () => {
  it('names the section by the longest matching link', () => {
    expect(currentSection('/app/questions/abc', STUDY_LINKS).label).toBe('Questions')
    expect(currentSection('/app/notes/library', STUDY_LINKS).label).toBe('Notes')
    expect(currentSection('/app/mcq/sets/x', STUDY_LINKS).label).toBe('MCQ Bank')
  })
  it('is Home for /app and for pages that are not a section', () => {
    expect(currentSection('/app', STUDY_LINKS).label).toBe('Home')
    expect(currentSection('/app/', STUDY_LINKS).label).toBe('Home')
    expect(currentSection('/app/onboarding', STUDY_LINKS).label).toBe('Home')
  })
  it('does not match a link that merely shares a prefix of letters', () => {
    expect(currentSection('/app/notesy', STUDY_LINKS).label).toBe('Home')
  })
  it('names the public sections that share the frame', () => {
    expect(currentSection('/features/focus-timer', STUDY_LINKS).label).toBe('Features')
    expect(currentSection('/courses/cma/final', STUDY_LINKS).label).toBe('Courses')
    expect(currentSection('/', STUDY_LINKS).label).toBe('Home')
  })
  it('is Settings in the settings area', () => {
    expect(currentSection('/app/settings/focus', STUDY_LINKS).label).toBe('Settings')
    expect(currentSection('/app/account', STUDY_LINKS).label).toBe('Settings')
  })
})

describe('isSettingsPath', () => {
  it('covers the account page and every settings page', () => {
    expect(isSettingsPath('/app/account')).toBe(true)
    expect(isSettingsPath('/app/settings/notes/')).toBe(true)
    expect(isSettingsPath('/app/settings')).toBe(true)
    expect(isSettingsPath('/app/notes')).toBe(false)
  })
})

describe('settingsLabel', () => {
  it('drops the trailing word settings', () => {
    expect(settingsLabel({ to: '/app/settings/focus', label: 'Focus settings' })).toBe('Focus')
    expect(settingsLabel({ to: '/app/account', label: 'Account' })).toBe('Account')
  })
})
