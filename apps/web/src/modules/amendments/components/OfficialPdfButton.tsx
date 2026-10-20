import { ArrowUpRight, Button } from '@artha/design-system'

interface Props {
  officialUrl?: string | null
  sourcePage?: number | null
  className?: string
}

export function OfficialPdfButton({ officialUrl, sourcePage, className }: Props) {
  if (!officialUrl) return null

  const targetUrl = sourcePage ? `${officialUrl}#page=${sourcePage}` : officialUrl

  return (
    <Button
      variant="outline"
      size="sm"
      asChild
      className={`h-8 gap-1.5 text-xs font-normal text-muted-foreground hover:text-foreground ${className ?? ''}`}
    >
      <a href={targetUrl} target="_blank" rel="noopener noreferrer">
        <span>ICAI Source {sourcePage ? `(p. ${sourcePage})` : ''}</span>
        <ArrowUpRight className="h-3 w-3" />
      </a>
    </Button>
  )
}
