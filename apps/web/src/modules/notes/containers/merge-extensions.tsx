import type { ReaderExtensions } from './reader-extensions'

/**
 * Combines the reader's plug-ins from several owners (the annotation layer, the library's export and OCR). Top-bar actions
 * add up in order; for every other seam the last owner that sets it wins, because only one owner is meant to set each.
 */
export function mergeExtensions(...parts: Array<Partial<ReaderExtensions> | undefined>): ReaderExtensions {
  const merged: ReaderExtensions = {}
  const actions: Array<NonNullable<ReaderExtensions['topActions']>> = []
  for (const part of parts) {
    if (!part) continue
    const { topActions, ...rest } = part
    if (topActions) actions.push(topActions)
    for (const [key, value] of Object.entries(rest)) {
      if (value !== undefined) (merged as Record<string, unknown>)[key] = value
    }
  }
  if (actions.length === 1) merged.topActions = actions[0]
  else if (actions.length > 1)
    merged.topActions = (
      <>
        {actions.map((a, i) => (
          <span key={i} className="contents">
            {a}
          </span>
        ))}
      </>
    )
  return merged
}
