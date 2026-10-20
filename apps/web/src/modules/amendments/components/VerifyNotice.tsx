import { Alert } from '@artha/design-system'

interface Props {
  className?: string
}

export function VerifyNotice({ className }: Props) {
  return (
    <Alert variant="info" className={className}>
      <div>
        <span className="font-semibold text-foreground">4-Eye Verification Notice</span>
        <p className="mt-0.5 text-xs text-muted-foreground">
          Every statutory amendment card in this workspace has been verified against official ICAI publications and
          Ministry gazettes under our 4-eye editorial procedure.
        </p>
      </div>
    </Alert>
  )
}
