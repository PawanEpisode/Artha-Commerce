import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'

import corpus from './render-cases.json'
import RichTextImpl from './RichTextImpl'

interface Case {
  id: string
  markdown: string
  html_includes?: string[]
  html_excludes?: string[]
}

const render = (c: Case) => renderToStaticMarkup(<RichTextImpl markdown={c.markdown} profile="note" />)

describe('conformance (rendered HTML)', () => {
  it.each((corpus.cases as Case[]).map((c) => [c.id, c] as const))('%s', (_id, c) => {
    const html = render(c)
    for (const needle of c.html_includes ?? []) expect(html).toContain(needle)
    for (const needle of c.html_excludes ?? []) expect(html).not.toContain(needle)
  })
})

describe('RichTextImpl images', () => {
  const id = '3f2b8c1e-5a4d-4e9b-8c7a-1d2e3f4a5b6c'

  it('resolves an attachment to a URL and keeps the alt text', () => {
    const html = renderToStaticMarkup(
      <RichTextImpl
        markdown={`![Balance sheet](attachment:${id})`}
        profile="note"
        resolveImage={(a) => `https://cdn.test/${a}.webp`}
      />,
    )
    expect(html).toContain(`src="https://cdn.test/${id}.webp"`)
    expect(html).toContain('alt="Balance sheet"')
  })

  it('shows a calm placeholder when the image cannot be resolved (offline)', () => {
    const html = renderToStaticMarkup(<RichTextImpl markdown={`![Chart](attachment:${id})`} profile="note" />)
    expect(html).not.toContain('<img')
    expect(html).toContain('Image: Chart is not available right now.')
  })
})
