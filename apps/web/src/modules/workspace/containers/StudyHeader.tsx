import { Badge, PageHeader } from '@artha/design-system'
import { Link } from '@tanstack/react-router'

import { useBootstrap } from '~/modules/personalization'

import { examChip, headline } from '../lib/greeting'

/** "Good evening, Aarav" and the exam countdown chip. The chip links to the date when it is still missing. */
export function StudyHeader() {
  const { data } = useBootstrap()
  const chip = examChip(data?.course ?? null)
  return (
    <PageHeader
      title={headline(new Date().getHours(), data?.first_name ?? '')}
      actions={
        data ? (
          chip.dated ? (
            <Badge variant="accent" className="h-auto max-w-full text-left leading-snug whitespace-normal">
              {chip.text}
            </Badge>
          ) : (
            <Link
              to="/app/onboarding"
              search={{ step: 'course' }}
              className="text-[13px] font-medium text-primary underline-offset-4 hover:underline"
            >
              {chip.text}
            </Link>
          )
        ) : null
      }
    />
  )
}
