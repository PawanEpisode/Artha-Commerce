import { type RefObject, useEffect } from 'react'

import { track } from '~/modules/observability'

const SETTLE_MS = 2000

/**
 * `workspace_viewed` (PRD 10): once per visit, after the widgets had a moment to load or hide, with the ones on screen.
 * Read from the DOM so each widget keeps owning its own visibility rules.
 */
export function useWorkspaceViewed(root: RefObject<HTMLElement | null>) {
  useEffect(() => {
    const timer = setTimeout(() => {
      const shown = [...(root.current?.querySelectorAll<HTMLElement>('[data-widget]') ?? [])]
        .filter((el) => el.getAttribute('aria-busy') !== 'true')
        .map((el) => (el.dataset.widget ?? '').replace('widget-', ''))
      track('workspace_viewed', { widgets_shown: shown, has_due: shown.includes('revision') })
    }, SETTLE_MS)
    return () => clearTimeout(timer)
  }, [root])
}

export const trackWidgetClicked = (widget: string) => track('workspace_widget_clicked', { widget })
