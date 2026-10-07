import type { Options as MarkdownOptions } from 'react-markdown'
import rehypeKatex from 'rehype-katex'
import rehypeSanitize, { defaultSchema } from 'rehype-sanitize'
import remarkGfm from 'remark-gfm'
import remarkMath from 'remark-math'

import type { RichTextProfile } from './profiles'

/**
 * One remark/rehype pipeline for every rich-text surface (notes now, the question bank later), so the same Markdown
 * renders the same everywhere. Order matters: sanitise the tree first (raw HTML never passes), then let KaTeX turn the
 * `language-math` nodes into markup, because the sanitiser would strip KaTeX's own spans.
 */
const schema = {
  ...defaultSchema,
  attributes: {
    ...defaultSchema.attributes,
    code: [...(defaultSchema.attributes?.code ?? []), ['className', 'language-math', 'math-inline', 'math-display']],
    // GFM task lists render a disabled checkbox.
    input: [['type', 'checkbox'], ['checked'], ['disabled']],
  },
  tagNames: [...(defaultSchema.tagNames ?? []), 'input'],
  // Note images are `attachment:<id>`; the page swaps them for a signed URL when it renders.
  // Same rule as the server linter: links are https only, images are attachments only (never fetched from elsewhere).
  protocols: { ...defaultSchema.protocols, href: ['https'], src: ['attachment'] },
}

/** Only attachments (`attachment:<id>`), https links and in-page anchors survive; everything else becomes an empty URL. */
export function urlTransform(url: string): string {
  if (/^attachment:[0-9a-f-]{36}$/i.test(url)) return url
  if (/^(https:|#)/i.test(url)) return url
  return ''
}

export function pipelineFor(
  _profile: RichTextProfile,
): Pick<MarkdownOptions, 'remarkPlugins' | 'rehypePlugins' | 'urlTransform'> {
  return {
    remarkPlugins: [remarkGfm, [remarkMath, { singleDollarTextMath: true }]],
    rehypePlugins: [
      [rehypeSanitize, schema],
      // Never throw on a half-typed formula; show the source in the error colour instead. `trust` stays off.
      [
        rehypeKatex,
        {
          throwOnError: false,
          errorColor: 'var(--destructive)',
          strict: 'ignore',
          trust: false,
          output: 'htmlAndMathml',
          maxSize: 20,
          maxExpand: 500,
        },
      ],
    ],
    urlTransform,
  }
}
