import { Share, SquarePlus } from '@artha/design-system'

/**
 * The three steps to put Artha on an iPhone or iPad Home Screen. One copy for everything that explains it: the alerts
 * step (where it is needed for push) and the install offer on the focus page.
 */
export function InstallSteps() {
  return (
    <ol className="list-decimal space-y-3 pl-5 marker:font-semibold">
      <li>
        Open this page in Safari and tap the Share button{' '}
        <Share aria-hidden className="inline size-4 align-text-bottom" /> at the bottom of the screen.
      </li>
      <li>
        Scroll down and choose <strong>Add to Home Screen</strong>{' '}
        <SquarePlus aria-hidden className="inline size-4 align-text-bottom" />, then tap Add.
      </li>
      <li>Open Artha from your Home Screen. This page will be right here, ready for the last tap.</li>
    </ol>
  )
}
