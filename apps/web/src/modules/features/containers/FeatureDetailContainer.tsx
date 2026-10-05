import type { Feature } from '~/modules/catalog'
import { features } from '~/modules/catalog'
import { track } from '~/modules/observability'

import { FeatureDetail } from '../components/FeatureDetail'
import type { OpenDestination } from '../components/OfferLink'
import { useFeatureViewer } from '../hooks/useFeatureViewer'
import { groupFeatures, offerFor } from '../lib/offers'

export function FeatureDetailContainer({ feature }: { feature: Feature }) {
  const viewer = useFeatureViewer()
  const offer = offerFor(feature, viewer)
  const { ready: available } = groupFeatures(features, viewer)
  const alternatives = available.filter((item) => item.feature.slug !== feature.slug).slice(0, 3)
  return (
    <FeatureDetail
      feature={feature}
      offer={offer}
      alternatives={offer.destination === 'soon' ? alternatives : []}
      onOpen={(slug, destination: OpenDestination) => track('feature_opened', { slug, destination })}
    />
  )
}
