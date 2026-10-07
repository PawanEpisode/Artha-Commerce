import { cn } from '@artha/design-system'
import { lazy, Suspense } from 'react'

import type { RichTextProfile } from './profiles'
import type { RichTextImplProps } from './RichTextImpl'
import { plainText } from './text'

const Impl = lazy(() => import('./RichTextImpl'))

interface RichTextProps extends Omit<RichTextImplProps, 'profile'> {
  /** What the body may contain. Notes use `note`. */
  profile?: RichTextProfile
  className?: string
}

/**
 * Renders sanitised Markdown with KaTeX in the shared reading style. The renderer loads on demand; until it arrives
 * the plain text shows, so there is no empty flash and no layout jump.
 */
export function RichText({ markdown, profile = 'note', resolveImage, className }: RichTextProps) {
  return (
    <div data-slot="rich-text" className={cn('prose-reading rich-text break-words', className)}>
      <Suspense fallback={<p className="whitespace-pre-wrap">{plainText(markdown)}</p>}>
        <Impl markdown={markdown} profile={profile} resolveImage={resolveImage} />
      </Suspense>
    </div>
  )
}
