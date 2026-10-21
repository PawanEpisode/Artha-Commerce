import { createFileRoute, Navigate } from '@tanstack/react-router'

import { buildHead } from '~/modules/seo'

export const Route = createFileRoute('/app/materials')({
  head: () =>
    buildHead({
      title: 'Institute Study Material & Checklists',
      description: 'Redirecting to Study Material',
      path: '/app/materials',
      noindex: true,
    }),
  component: function MaterialsRedirectRoute() {
    return <Navigate to="/app/material" replace />
  },
})
