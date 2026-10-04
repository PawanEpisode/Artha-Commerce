import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@artha/design-system'
import type { ReactNode } from 'react'

interface AuthCardProps {
  title: string
  description?: ReactNode
  children: ReactNode
  /** Links under the card body, for example "Already have an account? Sign in". */
  footer?: ReactNode
}

/** Shared shell for every auth screen: one width, one rhythm, works from 320 px up. */
export function AuthCard({ title, description, children, footer }: AuthCardProps) {
  return (
    <Card className="w-full max-w-md">
      <CardHeader className="text-center">
        <CardTitle className="text-2xl">{title}</CardTitle>
        {description && <CardDescription>{description}</CardDescription>}
      </CardHeader>
      <CardContent className="space-y-5">
        {children}
        {footer && <div className="text-center text-sm text-muted-foreground">{footer}</div>}
      </CardContent>
    </Card>
  )
}
