import { Button, type ButtonProps, cn } from '@artha/design-system'
import { Link } from '@tanstack/react-router'
import type { ComponentProps } from 'react'

import type { LiveToolPath } from '~/modules/catalog'

import type { FeatureOffer } from '../lib/offers'

export type OpenDestination = 'app' | 'login' | 'browse'

interface Props {
  offer: FeatureOffer
  size?: ButtonProps['size']
  variant?: ButtonProps['variant']
  /** Show the trailing arrow. Defaults on, every offer navigates. */
  arrow?: boolean
  fullWidth?: boolean
  className?: string
  onOpen: (slug: string, destination: OpenDestination) => void
}

type LinkPassThrough = Omit<ComponentProps<typeof Link>, 'to'>

/**
 * The button's `asChild` styles land on this component, so they must be forwarded to the anchor.
 * A wrapper that drops `className` leaves the signed-in link as plain text and wraps the arrow.
 */
function AppPathLink({ path, ...props }: { path: string } & LinkPassThrough) {
  switch (path as LiveToolPath) {
    case '/app/focus':
      return <Link to="/app/focus" {...props} />
    case '/app/syllabus':
      return <Link to="/app/syllabus" {...props} />
    case '/app/tracker':
      return <Link to="/app/tracker" {...props} />
    case '/app/tracker/reports':
      return <Link to="/app/tracker/reports" {...props} />
    default:
      return null
  }
}

/** The primary action for a shipped feature: open the tool, or sign in and come back to it. */
export function OfferButton({
  offer,
  size = 'default',
  variant = 'cta',
  arrow = true,
  fullWidth = false,
  className,
  onOpen,
}: Props) {
  if (offer.destination === 'soon') return null
  const destination = offer.destination
  const onClick = () => onOpen(offer.feature.slug, destination)
  const label = <span className="min-w-0 text-balance">{offer.label}</span>
  const link =
    offer.destination === 'login' && offer.nextPath ? (
      <Link to="/login" search={{ next: offer.nextPath }} onClick={onClick}>
        {label}
      </Link>
    ) : (
      <AppPathLink path={offer.appPath ?? ''} onClick={onClick}>
        {label}
      </AppPathLink>
    )
  if (!link) return null
  return (
    <Button
      variant={variant}
      size={size}
      arrow={arrow}
      fullWidth={fullWidth}
      className={cn('h-auto max-w-full min-w-0 py-2.5 whitespace-normal', className)}
      asChild
    >
      {link}
    </Button>
  )
}

/** The secondary action next to an offer, e.g. "Browse the syllabus". */
export function BrowseButton({
  offer,
  fullWidth = false,
  className,
  onOpen,
}: Omit<Props, 'size' | 'variant' | 'arrow'>) {
  if (!offer.browse) return null
  return (
    <Button variant="outline" arrow fullWidth={fullWidth} className={className} asChild>
      <Link to="/courses" onClick={() => onOpen(offer.feature.slug, 'browse')}>
        {offer.browse.label}
      </Link>
    </Button>
  )
}
