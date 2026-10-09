import { Fragment } from 'react'

import { tokenize } from '../lib/inline'

/** Card text as React nodes: paragraphs, line breaks, bold, italic and code. Never HTML. */
export function InlineText({ text }: { text: string }) {
  return (
    <>
      {tokenize(text).map((paragraph, p) => (
        <p key={p} className="text-balance break-words">
          {paragraph.map((line, l) => (
            <Fragment key={l}>
              {l > 0 ? <br /> : null}
              {line.map((part, i) =>
                part.kind === 'bold' ? (
                  <strong key={i}>{part.text}</strong>
                ) : part.kind === 'italic' ? (
                  <em key={i}>{part.text}</em>
                ) : part.kind === 'code' ? (
                  <code key={i} className="rounded bg-muted px-1 py-0.5 font-mono text-[0.9em]">
                    {part.text}
                  </code>
                ) : (
                  <Fragment key={i}>{part.text}</Fragment>
                ),
              )}
            </Fragment>
          ))}
        </p>
      ))}
    </>
  )
}
