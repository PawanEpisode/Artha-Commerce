import { Badge, Button, Container, ease, Flame, Sparkles } from '@artha/design-system'
import { Link } from '@tanstack/react-router'
import { motion } from 'motion/react'

function ProductPeek() {
  const tasks = [
    { t: 'Advanced Accounting: AS 19 Leases', d: true },
    { t: 'Taxation: GST input tax credit', d: true },
    { t: '20 MCQs: Company Law', d: false },
  ]
  return (
    <div aria-hidden className="relative mx-auto mt-16 w-full max-w-3xl">
      <div className="absolute -inset-x-8 -inset-y-6 -z-10 rounded-[2rem] bg-gradient-to-br from-primary/20 via-accent/15 to-highlight/20 blur-2xl" />
      <div className="rounded-2xl border bg-card p-5 shadow-lift sm:p-7">
        <div className="mb-5 flex items-center justify-between text-left">
          <div>
            <p className="text-xs text-muted-foreground">Today · sample preview</p>
            <p className="font-display text-xl font-bold">Good morning, aspirant</p>
          </div>
          <Badge variant="highlight">
            <Flame /> 12 day streak
          </Badge>
        </div>
        <div className="grid gap-5 sm:grid-cols-[auto_1fr] sm:items-center">
          <div className="relative mx-auto size-32">
            <svg viewBox="0 0 120 120" className="size-full -rotate-90">
              <circle cx="60" cy="60" r="52" fill="none" strokeWidth="10" className="stroke-muted" />
              <motion.circle
                cx="60"
                cy="60"
                r="52"
                fill="none"
                strokeWidth="10"
                strokeLinecap="round"
                className="stroke-primary"
                strokeDasharray={327}
                initial={{ strokeDashoffset: 327 }}
                animate={{ strokeDashoffset: 327 * (1 - 0.68) }}
                transition={{ duration: 1.4, ease, delay: 0.5 }}
              />
            </svg>
            <div className="absolute inset-0 grid place-items-center text-center">
              <div>
                <p className="font-display text-3xl font-extrabold">68%</p>
                <p className="text-[11px] text-muted-foreground">readiness</p>
              </div>
            </div>
          </div>
          <ul className="space-y-2.5">
            {tasks.map((task) => (
              <li
                key={task.t}
                className="flex items-center gap-3 rounded-xl border bg-background px-4 py-3 text-left text-sm"
              >
                <span
                  className={`grid size-5 place-items-center rounded-full text-[11px] ${task.d ? 'bg-accent text-accent-foreground' : 'border-2 border-border'}`}
                >
                  {task.d ? '✓' : ''}
                </span>
                <span className={task.d ? 'text-muted-foreground line-through' : 'font-medium'}>{task.t}</span>
              </li>
            ))}
          </ul>
        </div>
      </div>
      <motion.div
        className="absolute -right-3 -bottom-5 hidden rounded-xl border bg-card px-4 py-3 text-left shadow-lift sm:block"
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 1, duration: 0.6, ease }}
      >
        <p className="flex items-center gap-1.5 text-xs font-semibold text-primary">
          <Sparkles className="size-3.5" /> AI tip
        </p>
        <p className="mt-1 max-w-[190px] text-xs text-muted-foreground">Revise Ind AS 116 tomorrow to lock it in.</p>
      </motion.div>
    </div>
  )
}

export function Hero() {
  return (
    <section className="relative overflow-hidden pt-16 pb-20 sm:pt-24">
      <div aria-hidden className="bg-grid absolute inset-0 -z-10" />
      <Container className="text-center">
        <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.6, ease }}>
          <Badge variant="outline" className="mb-6">
            <Sparkles className="text-primary" /> Built for CA, CS and CMA aspirants
          </Badge>
          <h1 className="mx-auto max-w-4xl text-4xl leading-[1.05] font-extrabold sm:text-6xl lg:text-7xl">
            Your entire exam prep, <span className="text-gradient">in one calm workspace.</span>
          </h1>
          <p className="mx-auto mt-6 max-w-2xl text-lg text-muted-foreground sm:text-xl">
            Plan backwards from your exam date, track every chapter, practise with mocks and revise smarter. No more
            juggling notebooks, PDFs and WhatsApp groups.
          </p>
          <div className="mt-9 flex flex-col items-center justify-center gap-3 sm:flex-row">
            <Button size="lg" variant="cta" arrow asChild>
              <Link to="/login">Start preparing free</Link>
            </Button>
            <Button size="lg" variant="outline" arrow asChild>
              <a href="#planner">Build a sample plan</a>
            </Button>
          </div>
        </motion.div>
        <ProductPeek />
      </Container>
    </section>
  )
}
