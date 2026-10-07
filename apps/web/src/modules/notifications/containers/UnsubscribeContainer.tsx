import { useMutation, useQuery } from '@tanstack/react-query'

import { UnsubscribeView } from '../components/UnsubscribeView'
import { confirmUnsubscribe, previewUnsubscribe } from '../lib/api'
import { notificationKeys } from '../lib/keys'
import { unsubscribeStatus } from '../lib/unsubscribe'

/**
 * The page behind the link in the weekly email. Public: the signed token in the URL is the credential, so there is no
 * sign-in and no feature flag (a student who asks to stop is always honoured). It asks for one click rather than acting
 * on load, so a mail scanner that opens the link cannot unsubscribe anyone.
 */
export function UnsubscribeContainer({ token }: { token: string | undefined }) {
  const preview = useQuery({
    queryKey: notificationKeys.unsubscribe(token ?? ''),
    queryFn: () => previewUnsubscribe(token as string),
    enabled: Boolean(token),
    retry: false,
    staleTime: Infinity,
  })
  const confirm = useMutation({ mutationFn: () => confirmUnsubscribe(token as string) })

  const status = unsubscribeStatus({
    token,
    previewLoading: preview.isPending && Boolean(token),
    previewError: preview.error,
    confirming: confirm.isPending,
    confirmed: confirm.isSuccess,
    confirmError: confirm.error,
  })
  return (
    <UnsubscribeView
      status={status}
      label={confirm.data?.label ?? preview.data?.label}
      onConfirm={() => confirm.mutate()}
    />
  )
}
