import type { Feature, FeatureFlagName, LiveToolPath } from '~/modules/catalog'

export interface FeatureViewer {
  signedIn: boolean
  flags: Record<FeatureFlagName, boolean>
}

export type FeatureDestination = 'app' | 'login' | 'soon'

export interface FeatureOffer {
  feature: Feature
  destination: FeatureDestination
  label: string
  appPath?: LiveToolPath
  nextPath?: string
  browse?: { to: '/courses'; label: string }
}

const signInLabel = (cta: string) => `Sign in to ${cta.charAt(0).toLowerCase()}${cta.slice(1)}`

/** What the primary button on a feature should do for this student. */
export function offerFor(feature: Feature, viewer: FeatureViewer): FeatureOffer {
  if (feature.status !== 'live' || viewer.flags[feature.tool.flag] === false) {
    return { feature, destination: 'soon', label: 'Coming soon' }
  }
  const browse = feature.tool.browse
  if (!viewer.signedIn) {
    return {
      feature,
      destination: 'login',
      label: signInLabel(feature.tool.cta),
      nextPath: feature.tool.to,
      browse,
    }
  }
  return { feature, destination: 'app', label: feature.tool.cta, appPath: feature.tool.to, browse }
}

/** Shipped tools first (catalog order), then anything still unbuilt or switched off. */
export function groupFeatures(list: readonly Feature[], viewer: FeatureViewer) {
  const ready: FeatureOffer[] = []
  const soon: FeatureOffer[] = []
  for (const feature of list) {
    const offer = offerFor(feature, viewer)
    if (offer.destination === 'soon') soon.push(offer)
    else ready.push(offer)
  }
  return { ready, soon }
}
