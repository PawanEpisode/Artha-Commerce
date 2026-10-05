import { createFileRoute } from '@tanstack/react-router'

import { faqItems, LandingPage } from '~/modules/landing'
import { LANDING_REDIRECT_SCRIPT } from '~/modules/personalization'
import { pageHead } from '~/modules/seo'

export const Route = createFileRoute('/')({
  head: () => {
    const head = pageHead('/', { faq: faqItems })
    // Signed-in students skip the marketing page before it paints. Signed-out HTML is unchanged (see the module).
    return { ...head, scripts: [...(head.scripts ?? []), { children: LANDING_REDIRECT_SCRIPT }] }
  },
  component: LandingPage,
})
