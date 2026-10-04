import { Button } from '@artha/design-system'

/** "or" divider plus the Google button, shared by sign in and sign up. */
export function GoogleButton({ onClick, disabled }: { onClick: () => void; disabled?: boolean }) {
  return (
    <>
      <Button type="button" variant="outline" className="w-full" onClick={onClick} disabled={disabled}>
        Continue with Google
      </Button>
      <div className="flex items-center gap-3 text-xs text-muted-foreground" aria-hidden>
        <span className="h-px flex-1 bg-border" /> or <span className="h-px flex-1 bg-border" />
      </div>
    </>
  )
}
