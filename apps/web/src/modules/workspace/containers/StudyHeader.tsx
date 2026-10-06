import { Badge } from '@artha/design-system'
import { Link } from '@tanstack/react-router'

import { useBootstrap } from '~/modules/personalization'

import { examChip, headline } from '../lib/greeting'

/** "Good evening, Aarav" and the exam countdown chip. The chip links to the date when it is still missing. */
export function StudyHeader() {
  const { data } = useBootstrap()
  const chip = examChip(data?.course ?? null)
  return (
    <header className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
      <h1 className="text-3xl font-extrabold">{headline(new Date().getHours(), data?.first_name ?? '')}</h1>
      {data ? (
        chip.dated ? (
          <Badge variant="accent" className="self-start sm:self-auto">
            {chip.text}
          </Badge>
        ) : (
          <Link
            to="/app/onboarding"
            search={{ step: 'course' }}
            className="self-start text-sm font-semibold text-primary underline-offset-4 hover:underline sm:self-auto"
          >
            {chip.text}
          </Link>
        )
      ) : null}
    </header>
  )
}
