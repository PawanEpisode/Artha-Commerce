import { Button, Card, CardContent, CardDescription, CardHeader, CardTitle, Input } from '@artha/design-system'
import { Mail } from 'lucide-react'
import type { FormEvent } from 'react'

interface LoginCardProps {
  email: string
  onEmailChange: (v: string) => void
  onSubmitEmail: (e: FormEvent) => void
  onGoogle: () => void
  status: 'idle' | 'sending' | 'sent' | 'error'
  message?: string
  disabled?: boolean
}

/** Presentational only: no hooks, no data fetching. State lives in LoginContainer. */
export function LoginCard({
  email,
  onEmailChange,
  onSubmitEmail,
  onGoogle,
  status,
  message,
  disabled,
}: LoginCardProps) {
  return (
    <Card className="w-full max-w-md">
      <CardHeader className="text-center">
        <CardTitle className="text-2xl">Welcome to ArthaCommerce</CardTitle>
        <CardDescription>Sign in to save your plan, notes and progress.</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <Button variant="outline" className="w-full" onClick={onGoogle} disabled={disabled}>
          Continue with Google
        </Button>
        <div className="flex items-center gap-3 text-xs text-muted-foreground">
          <span className="h-px flex-1 bg-border" /> or <span className="h-px flex-1 bg-border" />
        </div>
        {status === 'sent' ? (
          <p role="status" className="rounded-lg bg-accent/15 p-4 text-sm">
            Check your inbox. We sent a sign-in link to <strong>{email}</strong>.
          </p>
        ) : (
          <form onSubmit={onSubmitEmail} className="space-y-3">
            <Input
              type="email"
              required
              autoComplete="email"
              placeholder="you@example.com"
              value={email}
              onChange={(e) => onEmailChange(e.target.value)}
              disabled={disabled}
            />
            <Button type="submit" className="w-full" disabled={disabled || status === 'sending'}>
              <Mail /> {status === 'sending' ? 'Sending link…' : 'Email me a sign-in link'}
            </Button>
          </form>
        )}
        {message && (
          <p role="alert" className="text-sm text-destructive">
            {message}
          </p>
        )}
      </CardContent>
    </Card>
  )
}
