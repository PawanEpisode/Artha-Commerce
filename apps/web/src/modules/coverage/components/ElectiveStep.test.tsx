import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import type { ElectiveSlotInfo } from '~/modules/syllabus'

import { ElectiveStep } from './OnboardingSteps'

const slots: ElectiveSlotInfo[] = [
  {
    key: 'paper-20',
    name: 'Paper 20',
    paper_number: 20,
    group_key: null,
    options: [
      { id: 's-a', key: 'a', name: 'Corporate Financial Reporting' },
      { id: 's-b', key: 'b', name: 'Strategic Performance Management' },
    ],
  },
  {
    key: 'paper-21',
    name: 'Paper 21',
    paper_number: 21,
    group_key: null,
    options: [{ id: 's-c', key: 'c', name: 'Direct Tax Laws' }],
  },
]

function setup(overrides: Partial<Parameters<typeof ElectiveStep>[0]> = {}) {
  const props = {
    slots,
    choices: {},
    pending: false,
    onChoose: vi.fn(),
    onBack: vi.fn(),
    onSubmit: vi.fn(),
    ...overrides,
  }
  render(<ElectiveStep {...props} />)
  return props
}

describe('ElectiveStep', () => {
  it('shows one group per elective paper, with every option and a "decide later" choice', () => {
    setup()
    expect(screen.getByRole('radiogroup', { name: 'Paper 20' })).toBeInTheDocument()
    expect(screen.getByRole('radiogroup', { name: 'Paper 21' })).toBeInTheDocument()
    expect(screen.getByRole('radio', { name: /Corporate Financial Reporting/ })).toBeInTheDocument()
    expect(screen.getByRole('radio', { name: /Strategic Performance Management/ })).toBeInTheDocument()
    expect(screen.getAllByRole('radio', { name: /I will decide later/ })).toHaveLength(2)
  })

  it('starts on "decide later" for a paper nothing was chosen for', () => {
    setup()
    const group = screen.getByRole('radiogroup', { name: 'Paper 20' })
    expect(group.querySelector('[aria-checked="true"]')).toHaveTextContent('I will decide later')
  })

  it('reports the chosen option with its slot key', async () => {
    const { onChoose } = setup()
    await userEvent.click(screen.getByRole('radio', { name: /Strategic Performance Management/ }))
    expect(onChoose).toHaveBeenCalledWith('paper-20', 's-b')
  })

  it('reports null when a choice is taken back with "decide later"', async () => {
    const { onChoose } = setup({ choices: { 'paper-20': 's-a' } })
    const group = screen.getByRole('radiogroup', { name: 'Paper 20' })
    expect(group.querySelector('[aria-checked="true"]')).toHaveTextContent('Corporate Financial Reporting')
    await userEvent.click(screen.getAllByRole('radio', { name: /I will decide later/ })[0]!)
    expect(onChoose).toHaveBeenCalledWith('paper-20', null)
  })

  it('submits and goes back through its buttons', async () => {
    const { onSubmit, onBack } = setup()
    await userEvent.click(screen.getByRole('button', { name: 'Create my syllabus map' }))
    await userEvent.click(screen.getByRole('button', { name: 'Back' }))
    expect(onSubmit).toHaveBeenCalledTimes(1)
    expect(onBack).toHaveBeenCalledTimes(1)
  })

  it('locks the form while saving and shows an error', () => {
    setup({ pending: true, error: 'We could not create your syllabus map.' })
    expect(screen.getByRole('button', { name: /Create my syllabus map/ })).toBeDisabled()
    expect(screen.getByRole('button', { name: 'Back' })).toBeDisabled()
    expect(screen.getByRole('alert')).toHaveTextContent('We could not create your syllabus map.')
  })
})
