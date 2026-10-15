import {
  Card,
  Combobox,
  Countdown,
  NumberGrid,
  type NumberGridItem,
  SegmentedBar,
  TagInput,
} from '@artha/design-system'
import { useState } from 'react'

export function PracticePrimitivesShowcase() {
  const [comboboxSingle, setComboboxSingle] = useState('mcq_single')
  const [comboboxMulti, setComboboxMulti] = useState<string[]>(['dt', 'gst'])
  const [tags, setTags] = useState(['Taxation', 'Direct Tax', 'Section 17(5)'])
  const [currentIndex, setCurrentIndex] = useState(2)

  const paletteItems: NumberGridItem[] = [
    { id: 1, number: 1, state: 'correct' },
    { id: 2, number: 2, state: 'incorrect' },
    { id: 3, number: 3, state: 'answered' },
    { id: 4, number: 4, state: 'marked' },
    { id: 5, number: 5, state: 'answered_marked' },
    { id: 6, number: 6, state: 'seen' },
    { id: 7, number: 7, state: 'unseen' },
    { id: 8, number: 8, state: 'skipped' },
    { id: 9, number: '9.1', state: 'seen' },
    { id: 10, number: '9.2', state: 'unseen' },
  ]

  const segmentItems = [
    { key: 'correct', value: 7, label: 'Correct', variant: 'success' as const },
    { key: 'incorrect', value: 2, label: 'Incorrect', variant: 'destructive' as const },
    { key: 'skipped', value: 1, label: 'Skipped', variant: 'warning' as const },
  ]

  return (
    <section className="space-y-6">
      <div className="space-y-1">
        <h2 className="text-xl font-bold">Practice & Question Bank Primitives</h2>
        <p className="text-sm text-muted-foreground">
          Combobox, TagInput, NumberGrid palette, Countdown timer, and SegmentedBar used across browsing and practice.
        </p>
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        <Card className="space-y-3 p-4">
          <h3 className="text-sm font-semibold">Combobox</h3>
          <div className="space-y-3">
            <div>
              <p className="mb-1 text-xs text-muted-foreground">Single selection (Kind)</p>
              <Combobox
                value={comboboxSingle}
                onChange={(val) => setComboboxSingle(val as string)}
                options={[
                  { value: 'mcq_single', label: 'Single Choice MCQ', badge: '1 mark' },
                  { value: 'mcq_multi', label: 'Multiple Choice MCQ', badge: '2 marks' },
                  { value: 'numeric', label: 'Numeric Answer' },
                  { value: 'case_study', label: 'Case Study' },
                ]}
              />
            </div>
            <div>
              <p className="mb-1 text-xs text-muted-foreground">Multi selection (Subjects)</p>
              <Combobox
                multiple
                value={comboboxMulti}
                onChange={(val) => setComboboxMulti(val as string[])}
                options={[
                  { value: 'dt', label: 'Direct Tax', badge: 'Paper 7' },
                  { value: 'gst', label: 'Indirect Tax (GST)', badge: 'Paper 7' },
                  { value: 'law', label: 'Corporate Law', badge: 'Paper 6' },
                  { value: 'cost', label: 'Cost Accounting', badge: 'Paper 8' },
                ]}
              />
            </div>
          </div>
        </Card>

        <Card className="space-y-3 p-4">
          <h3 className="text-sm font-semibold">TagInput</h3>
          <p className="text-xs text-muted-foreground">Type + Enter or comma to add, backspace to remove.</p>
          <TagInput value={tags} onChange={setTags} placeholder="Add chapter or concept tag..." />
        </Card>
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        <Card className="space-y-3 p-4">
          <h3 className="text-sm font-semibold">NumberGrid (Question Palette)</h3>
          <p className="text-xs text-muted-foreground">
            Current question is #{paletteItems[currentIndex].number}. Displays all states with accessible labels and
            icons.
          </p>
          <NumberGrid items={paletteItems} currentIndex={currentIndex} onSelect={setCurrentIndex} columns={5} />
        </Card>

        <Card className="space-y-4 p-4">
          <h3 className="text-sm font-semibold">Countdown Timer & SegmentedBar</h3>
          <div className="flex flex-wrap items-center gap-4">
            <div>
              <p className="mb-1 text-xs text-muted-foreground">Normal</p>
              <Countdown secondsRemaining={1240} />
            </div>
            <div>
              <p className="mb-1 text-xs text-muted-foreground">Warning (&lt; 5m)</p>
              <Countdown secondsRemaining={240} />
            </div>
            <div>
              <p className="mb-1 text-xs text-muted-foreground">Danger (&lt; 1m)</p>
              <Countdown secondsRemaining={45} />
            </div>
            <div>
              <p className="mb-1 text-xs text-muted-foreground">Paused</p>
              <Countdown secondsRemaining={600} isPaused />
            </div>
          </div>

          <div className="pt-2">
            <p className="mb-1.5 text-xs text-muted-foreground">SegmentedBar (Score distribution)</p>
            <SegmentedBar label="Session results" segments={segmentItems} total={10} showLegend showValues />
          </div>
        </Card>
      </div>
    </section>
  )
}
