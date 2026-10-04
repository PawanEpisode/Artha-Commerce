import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
  Badge,
  Button,
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
  Container,
  Input,
  Logo,
  Reveal,
  Tabs,
  TabsList,
  TabsTrigger,
} from '@artha/design-system'

const swatches = [
  ['background', 'bg-background'],
  ['foreground', 'bg-foreground'],
  ['card', 'bg-card'],
  ['primary', 'bg-primary'],
  ['secondary', 'bg-secondary'],
  ['muted', 'bg-muted'],
  ['accent', 'bg-accent'],
  ['highlight', 'bg-highlight'],
  ['destructive', 'bg-destructive'],
  ['border', 'bg-border'],
] as const

function Block({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="space-y-4">
      <h2 className="text-xl font-bold">{title}</h2>
      {children}
    </section>
  )
}

/** Living style guide for @artha/design-system. Every primitive appears here in all its variants. */
export function DesignShowcase() {
  return (
    <Container className="space-y-12 py-14">
      <header className="space-y-3">
        <Logo />
        <h1 className="text-4xl font-extrabold">Design system</h1>
        <p className="max-w-2xl text-muted-foreground">
          Tokens and primitives from <code>packages/design-system</code>. Toggle the theme in the header to check both
          modes.
        </p>
      </header>

      <Block title="Colour tokens">
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-5">
          {swatches.map(([name, cls]) => (
            <div key={name} className="space-y-2">
              <div className={`h-16 rounded-lg border ${cls}`} />
              <p className="text-xs font-medium">{name}</p>
            </div>
          ))}
        </div>
      </Block>

      <Block title="Typography">
        <div className="space-y-2">
          <p className="font-display text-5xl font-extrabold">Display 5xl</p>
          <p className="font-display text-3xl font-bold">Heading 3xl</p>
          <p className="text-lg">Body large, Inter Variable</p>
          <p className="text-sm text-muted-foreground">Small muted text</p>
        </div>
      </Block>

      <Block title="Buttons">
        <div className="flex flex-wrap items-center gap-3">
          <Button>Default</Button>
          <Button variant="accent">Accent</Button>
          <Button variant="secondary">Secondary</Button>
          <Button variant="outline">Outline</Button>
          <Button variant="ghost">Ghost</Button>
          <Button variant="link">Link</Button>
          <Button size="sm">Small</Button>
          <Button size="lg">Large</Button>
          <Button disabled>Disabled</Button>
        </div>
      </Block>

      <Block title="Badges">
        <div className="flex flex-wrap gap-2">
          <Badge>Default</Badge>
          <Badge variant="outline">Outline</Badge>
          <Badge variant="accent">Accent</Badge>
          <Badge variant="highlight">Highlight</Badge>
        </div>
      </Block>

      <Block title="Form">
        <div className="max-w-sm space-y-3">
          <Input placeholder="you@example.com" />
          <Input placeholder="Disabled" disabled />
        </div>
      </Block>

      <Block title="Card">
        <Card className="max-w-sm">
          <CardHeader>
            <CardTitle>Advanced Accounting</CardTitle>
            <CardDescription>68% covered</CardDescription>
          </CardHeader>
          <CardContent className="text-sm text-muted-foreground">Card content sits here.</CardContent>
        </Card>
      </Block>

      <Block title="Tabs">
        <Tabs defaultValue="ca">
          <TabsList>
            <TabsTrigger value="ca">CA</TabsTrigger>
            <TabsTrigger value="cs">CS</TabsTrigger>
            <TabsTrigger value="cma">CMA</TabsTrigger>
          </TabsList>
        </Tabs>
      </Block>

      <Block title="Accordion">
        <Accordion type="single" collapsible className="max-w-xl">
          <AccordionItem value="a">
            <AccordionTrigger>What is this?</AccordionTrigger>
            <AccordionContent>A primitive built on Radix with our tokens.</AccordionContent>
          </AccordionItem>
        </Accordion>
      </Block>

      <Block title="Motion">
        <Reveal>
          <Card className="max-w-sm p-6">Fades up when it enters the viewport and respects reduced motion.</Card>
        </Reveal>
      </Block>
    </Container>
  )
}
