import { render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import { mergeExtensions } from './merge-extensions'

describe('mergeExtensions', () => {
  it('adds up top-bar actions in order and lets each owner set its own seams', () => {
    const onSelection = vi.fn()
    const merged = mergeExtensions(
      { topActions: <button>Marks</button>, onSelection },
      { topActions: <button>Export</button> },
      undefined,
      { syncChip: <span>Saved</span> },
    )
    render(<div>{merged.topActions}</div>)
    expect(screen.getAllByRole('button').map((b) => b.textContent)).toEqual(['Marks', 'Export'])
    expect(merged.onSelection).toBe(onSelection)
    expect(merged.syncChip).toBeDefined()
  })

  it('leaves a single owner’s actions untouched and gives nothing when no one has any', () => {
    const only = <button>Only</button>
    expect(mergeExtensions({ topActions: only }).topActions).toBe(only)
    expect(mergeExtensions({}, undefined)).toEqual({})
  })
})
