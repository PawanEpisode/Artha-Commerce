import type { Feature, FeatureFlagName, LiveToolPath } from '~/modules/catalog'

export interface FeatureViewer {
  signedIn: boolean
  flags: Record<FeatureFlagName, boolean>
  /** Slugs of tools the student has already used. Unknown (guest, still loading) means no reordering. */
  used?: ReadonlySet<string>
  /** "CMA Final": names the student's course in the syllabus offer. */
  courseName?: string
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
  const label =
    viewer.courseName && feature.slug === 'syllabus-tracker'
      ? `Open your ${viewer.courseName} syllabus`
      : feature.tool.cta
  return { feature, destination: 'app', label, appPath: feature.tool.to, browse }
}

/**
 * Shipped tools first, then anything still unbuilt or switched off. Within the shipped ones a student sees the tools
 * they have not used yet before the ones they have (catalog order inside each group); everyone else gets catalog order.
 */
export function groupFeatures(list: readonly Feature[], viewer: FeatureViewer) {
  const ready: FeatureOffer[] = []
  const soon: FeatureOffer[] = []
  for (const feature of list) {
    const offer = offerFor(feature, viewer)
    if (offer.destination === 'soon') soon.push(offer)
    else ready.push(offer)
  }
  const used = viewer.used
  if (used && used.size > 0) {
    const unused = ready.filter((o) => !used.has(o.feature.slug))
    return { ready: [...unused, ...ready.filter((o) => used.has(o.feature.slug))], soon }
  }
  return { ready, soon }
}
