import { Reveal, Section } from '~/design-system'

const steps = [
  { n: '01', title: 'Tell us your goal', body: 'Choose your course, level and exam date. It takes under a minute.' },
  { n: '02', title: 'Follow your daily plan', body: 'Get a focused list for today: what to learn, revise and practise.' },
  { n: '03', title: 'Watch readiness grow', body: 'Every chapter you finish and every mock you attempt moves your readiness score.' },
]

export function HowItWorks() {
  return (
    <Section eyebrow="How it works" title="From overwhelmed to on track">
      <ol className="grid gap-8 md:grid-cols-3">
        {steps.map((s, i) => (
          <Reveal key={s.n} delay={i * 0.1}>
            <li className="relative list-none">
              <span className="font-display text-6xl font-extrabold text-primary/15">{s.n}</span>
              <h3 className="-mt-3 text-xl font-semibold">{s.title}</h3>
              <p className="mt-2 text-muted-foreground">{s.body}</p>
            </li>
          </Reveal>
        ))}
      </ol>
    </Section>
  )
}
