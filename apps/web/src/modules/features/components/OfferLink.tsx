import { Button, type ButtonProps } from '@artha/design-system'
import { Link } from '@tanstack/react-router'
import type { ReactNode } from 'react'

import type { FeatureOffer } from '../lib/offers'

export type OpenDestination = 'app' | 'login' | 'browse'

interface Props {
  offer: FeatureOffer
  size?: ButtonProps['size']
  variant?: ButtonProps['variant']
  /** Show the trailing arrow. Defaults on, every offer navigates. */
  arrow?: boolean
  className?: string
  onOpen: (slug: string, destination: OpenDestination) => void
}

function AppPathLink({ path, onClick, children }: { path: string; onClick: () => void; children: ReactNode }) {
  switch (path) {
    case '/app/focus':
      return (
        <Link to="/app/focus" onClick={onClick}>
          {children}
        </Link>
      )
    case '/app/syllabus':
      return (
        <Link to="/app/syllabus" onClick={onClick}>
          {children}
        </Link>
      )
    case '/app/tracker':
      return (
        <Link to="/app/tracker" onClick={onClick}>
          {children}
        </Link>
      )
    case '/app/tracker/reports':
      return (
        <Link to="/app/tracker/reports" onClick={onClick}>
          {children}
        </Link>
      )
    default:
      return null
  }
}

/** The primary action for a shipped feature: open the tool, or sign in and come back to it. */
export function OfferButton({ offer, size = 'default', variant = 'cta', arrow = true, className, onOpen }: Props) {
  if (offer.destination === 'soon') return null
  const destination = offer.destination
  const onClick = () => onOpen(offer.feature.slug, destination)
  const link =
    offer.destination === 'login' && offer.nextPath ? (
      <Link to="/login" search={{ next: offer.nextPath }} onClick={onClick}>
        {offer.label}
      </Link>
    ) : (
      <AppPathLink path={offer.appPath ?? ''} onClick={onClick}>
        {offer.label}
      </AppPathLink>
    )
  if (!link) return null
  return (
    <Button variant={variant} size={size} arrow={arrow} className={className} asChild>
      {link}
    </Button>
  )
}

/** The secondary action next to an offer, e.g. "Browse the syllabus". */
export function BrowseButton({ offer, className, onOpen }: Omit<Props, 'size' | 'variant' | 'arrow'>) {
  if (!offer.browse) return null
  return (
    <Button variant="outline" arrow className={className} asChild>
      <Link to="/courses" onClick={() => onOpen(offer.feature.slug, 'browse')}>
        {offer.browse.label}
      </Link>
    </Button>
  )
}
