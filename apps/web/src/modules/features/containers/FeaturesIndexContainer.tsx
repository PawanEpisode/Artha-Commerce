import { features } from '~/modules/catalog'
import { track } from '~/modules/observability'

import { FeaturesIndex } from '../components/FeaturesIndex'
import type { OpenDestination } from '../components/OfferLink'
import { useFeatureViewer } from '../hooks/useFeatureViewer'
import { groupFeatures } from '../lib/offers'

export function FeaturesIndexContainer() {
  const viewer = useFeatureViewer()
  const { ready: available, soon } = groupFeatures(features, viewer)
  return (
    <FeaturesIndex
      ready={available}
      soon={soon}
      onOpen={(slug, destination: OpenDestination) => track('feature_opened', { slug, destination })}
    />
  )
}
