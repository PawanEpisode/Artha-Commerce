import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { renderWithQuery } from '../test-utils'
import { ChapterPicker } from './ChapterPicker'

const h = vi.hoisted(() => ({ fetchCourses: vi.fn(), fetchLevel: vi.fn(), fetchSubject: vi.fn() }))
vi.mock('~/modules/syllabus', () => h)

const course = (code: string, levels: string[]) => ({
  id: code,
  code,
  name: code.toUpperCase(),
  institute_name: '',
  institute_url: '',
  description: '',
  levels: levels.map((l, i) => ({ id: `${code}-${l}`, code: l, name: `Level ${l}`, sort_order: i })),
})

beforeEach(() => {
  vi.clearAllMocks()
  h.fetchLevel.mockResolvedValue({ subjects: [{ key: 'p1', name: 'Paper 1' }] })
  h.fetchSubject.mockResolvedValue({
    chapters: [
      { id: 'ch1', name: 'Chapter One' },
      { id: 'ch2', name: 'Chapter Two' },
    ],
  })
})

async function choose(user: ReturnType<typeof userEvent.setup>, trigger: string, option: string) {
  await user.click(await screen.findByRole('combobox', { name: trigger }))
  await user.click(await screen.findByRole('option', { name: option }))
}

describe('the chapter picker', () => {
  it('skips the course and level steps when there is only one of each', async () => {
    const user = userEvent.setup()
    h.fetchCourses.mockResolvedValue([course('ca', ['inter'])])
    const onPick = vi.fn()
    renderWithQuery(<ChapterPicker onPick={onPick} />)
    expect(screen.queryByRole('combobox', { name: 'Course' })).toBeNull()
    await choose(user, 'Paper', 'Paper 1')
    await choose(user, 'Chapter', 'Chapter Two')
    expect(onPick).toHaveBeenLastCalledWith({ id: 'ch2', name: 'Chapter Two' })
    expect(h.fetchLevel).toHaveBeenCalledWith('ca', 'inter')
    expect(h.fetchSubject).toHaveBeenCalledWith('ca', 'inter', 'p1')
  })

  it('asks for the course and level when there are several, and clears the chapter when an earlier step changes', async () => {
    const user = userEvent.setup()
    h.fetchCourses.mockResolvedValue([course('ca', ['inter', 'final']), course('cma', ['final'])])
    const onPick = vi.fn()
    renderWithQuery(<ChapterPicker onPick={onPick} />)
    await choose(user, 'Course', 'CA')
    await choose(user, 'Level', 'Level inter')
    await choose(user, 'Paper', 'Paper 1')
    await choose(user, 'Chapter', 'Chapter One')
    expect(onPick).toHaveBeenLastCalledWith({ id: 'ch1', name: 'Chapter One' })
    await choose(user, 'Level', 'Level final')
    expect(onPick).toHaveBeenLastCalledWith(null)
    expect(screen.queryByRole('combobox', { name: 'Chapter' })).toBeNull()
  })

  it('says so when the syllabus cannot load', async () => {
    h.fetchCourses.mockRejectedValue(new Error('down'))
    renderWithQuery(<ChapterPicker onPick={vi.fn()} />)
    await waitFor(() => expect(screen.getByText(/could not load the syllabus/)).toBeInTheDocument())
  })
})
