import { describe, expect, it } from 'vitest'

import { markupDraft } from './mark-drafts'
import { fakeTextContent } from './pdf-engine/fake-engine'
import { selectionForHit } from './search-hit'

describe('highlight this search hit', () => {
  const content = fakeTextContent('Input tax credit is blocked for cars. Input tax credit again on page', 595, 842)

  it('turns the n-th match into the same selection a drag over the words would make', () => {
    const first = selectionForHit(3, content, 'tax credit', 0)
    const second = selectionForHit(3, content, 'tax credit', 1)
    expect(first?.selector.quote_exact).toBe('tax credit')
    expect(first?.rects.length).toBeGreaterThan(0)
    expect(second?.start).toBeGreaterThan(first?.start ?? 0)
    expect(markupDraft(second as NonNullable<typeof second>, 'highlight', 'y')).toMatchObject({
      kind: 'highlight',
      page: 3,
      quote_exact: 'tax credit',
    })
  })

  it('is null when the page no longer has that match', () => {
    expect(selectionForHit(3, content, 'tax credit', 5)).toBeNull()
    expect(selectionForHit(3, content, 'nothing here', 0)).toBeNull()
  })
})
