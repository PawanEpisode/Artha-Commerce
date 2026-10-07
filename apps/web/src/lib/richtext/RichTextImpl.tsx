import Markdown, { type Components } from 'react-markdown'

import { pipelineFor } from './pipeline'
import type { RichTextProfile } from './profiles'

export interface RichTextImplProps {
  markdown: string
  profile: RichTextProfile
  /** Maps an attachment id to a URL the browser can show, or undefined when it is not available (offline). */
  resolveImage?: (attachmentId: string) => string | undefined
}

/** The renderer proper. Loaded lazily by `RichText`, because react-markdown and KaTeX are heavy. */
export default function RichTextImpl({ markdown, profile, resolveImage }: RichTextImplProps) {
  const components: Components = {
    a: ({ href, children }) => (
      <a href={href} {...(href?.startsWith('#') ? {} : { target: '_blank', rel: 'noopener noreferrer' })}>
        {children}
      </a>
    ),
    // A wide table scrolls inside its own box, never the page.
    table: ({ children }) => (
      <div
        className="my-4 max-w-full overflow-x-auto"
        // eslint-disable-next-line jsx-a11y/no-noninteractive-tabindex -- a scrollable region must be reachable by keyboard
        tabIndex={0}
        role="region"
        aria-label="Table"
      >
        <table>{children}</table>
      </div>
    ),
    img: ({ src, alt }) => {
      const id = typeof src === 'string' && src.startsWith('attachment:') ? src.slice('attachment:'.length) : null
      // Only our own attachments are shown: an address typed into a note must never make the browser fetch it.
      const url = id ? resolveImage?.(id) : undefined
      if (!url) {
        return (
          <span className="my-2 inline-block rounded-lg border border-dashed border-border px-3 py-2 text-sm text-muted-foreground">
            {alt ? `Image: ${alt}` : 'Image'} is not available right now.
          </span>
        )
      }
      // Empty alt is a decision ("decorative"), so it stays empty instead of falling back to the file name.
      return <img src={url} alt={alt ?? ''} loading="lazy" className="my-3 h-auto max-w-full rounded-lg" />
    },
  }
  return (
    <Markdown {...pipelineFor(profile)} components={components}>
      {markdown}
    </Markdown>
  )
}
