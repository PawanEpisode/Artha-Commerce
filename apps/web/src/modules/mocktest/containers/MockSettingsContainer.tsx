import { CheckCircle2, Clock, Keyboard, Timer, TrendingUp } from '@artha/design-system'
import React, { useEffect, useState } from 'react'

import { fetchMockSettings, updateMockSettings } from '../lib/api'
import type { MockTestSettings } from '../lib/types'

export const MockSettingsContainer: React.FC = () => {
  const [settings, setSettings] = useState<MockTestSettings | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [isSaving, setIsSaving] = useState(false)
  const [saveSuccess, setSaveSuccess] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    setIsLoading(true)

    fetchMockSettings()
      .then((data) => {
        if (!cancelled) {
          setSettings(data)
          setIsLoading(false)
        }
      })
      .catch(() => {
        if (!cancelled) {
          setError('Failed to load settings.')
          setIsLoading(false)
        }
      })

    return () => {
      cancelled = true
    }
  }, [])

  const handleSave = async (updated: Partial<MockTestSettings>) => {
    if (!settings) return
    setIsSaving(true)
    setError(null)

    try {
      const saved = await updateMockSettings(updated)
      setSettings(saved)
      setSaveSuccess(true)
      setTimeout(() => setSaveSuccess(false), 2500)
    } catch {
      setError('Failed to save settings. Please try again.')
    } finally {
      setIsSaving(false)
    }
  }

  if (isLoading) {
    return (
      <div className="mx-auto max-w-3xl animate-pulse space-y-6 p-4 sm:p-8">
        <div className="h-20 rounded-2xl bg-muted/40" />
        <div className="h-44 rounded-2xl bg-muted/30" />
      </div>
    )
  }

  if (error && !settings) {
    return (
      <div className="mx-auto max-w-md space-y-4 p-8 text-center">
        <div className="rounded-2xl border border-rose-200 bg-rose-50 p-4 text-sm text-rose-700">{error}</div>
      </div>
    )
  }

  return (
    <div className="mx-auto max-w-3xl space-y-8 p-4 sm:p-8">
      {/* Header */}
      <div className="space-y-1 border-b pb-4">
        <div className="mb-2 inline-flex items-center gap-2 rounded-full bg-primary/10 px-3 py-1 text-xs font-semibold text-primary">
          <Timer className="h-3.5 w-3.5" />
          <span>Exam & CBT Preferences</span>
        </div>
        <h1 className="text-2xl font-bold tracking-tight text-foreground">Mock Tests & MTP Settings</h1>
        <p className="text-sm text-muted-foreground">
          Configure time accommodations, default exam modes, keyboard shortcuts, and cohort rankings.
        </p>
      </div>

      <div className="space-y-6">
        {/* Extra Time Accommodation */}
        <div className="space-y-4 rounded-2xl border bg-card p-5 shadow-xs sm:p-6">
          <div className="flex items-start gap-3">
            <Clock className="mt-0.5 h-5 w-5 shrink-0 text-primary" />
            <div className="space-y-1">
              <h2 className="text-base font-semibold text-foreground">Extra Time Accommodation (WCAG 2.2.1)</h2>
              <p className="text-xs leading-relaxed text-muted-foreground">
                If you have an official disability accommodation or require adjusted timing, exam clocks will
                automatically adjust (e.g., a 180-minute paper runs 225 minutes with +25%). Stored securely and never
                disclosed on peer leaderboards.
              </p>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-2 pt-2 sm:grid-cols-5">
            {[
              { val: 0, label: 'Standard (0%)' },
              { val: 10, label: '+10% Extra' },
              { val: 25, label: '+25% Extra' },
              { val: 50, label: '+50% Extra' },
              { val: 100, label: '+100% Extra' },
            ].map((opt) => {
              const isSelected = settings?.time_extension_pct === opt.val
              return (
                <button
                  key={opt.val}
                  type="button"
                  onClick={() => handleSave({ time_extension_pct: opt.val })}
                  disabled={isSaving}
                  className={`min-h-[44px] rounded-xl border px-3 py-2.5 text-xs font-semibold transition-all ${
                    isSelected
                      ? 'border-foreground bg-foreground text-background shadow-xs'
                      : 'border-border bg-background text-foreground hover:bg-muted'
                  }`}
                >
                  {opt.label}
                </button>
              )
            })}
          </div>
        </div>

        {/* Default Run Mode */}
        <div className="space-y-4 rounded-2xl border bg-card p-5 shadow-xs sm:p-6">
          <div className="space-y-1">
            <h2 className="text-base font-semibold text-foreground">Default Starting Mode</h2>
            <p className="text-xs text-muted-foreground">
              Choose the primary environment when you click "Start Attempt" on a paper.
            </p>
          </div>

          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <button
              type="button"
              onClick={() => handleSave({ default_run_mode: 'exam' })}
              disabled={isSaving}
              className={`min-h-[44px] rounded-xl border p-4 text-left transition-all ${
                settings?.default_run_mode === 'exam'
                  ? 'border-primary bg-primary/5 ring-1 ring-primary'
                  : 'border-border hover:bg-muted/30'
              }`}
            >
              <div className="text-sm font-semibold text-foreground">Official Timed Exam</div>
              <p className="mt-1 text-xs text-muted-foreground">
                Strict countdown timer, section locks, auto-save, and cohort percentile eligibility.
              </p>
            </button>

            <button
              type="button"
              onClick={() => handleSave({ default_run_mode: 'practice' })}
              disabled={isSaving}
              className={`min-h-[44px] rounded-xl border p-4 text-left transition-all ${
                settings?.default_run_mode === 'practice'
                  ? 'border-primary bg-primary/5 ring-1 ring-primary'
                  : 'border-border hover:bg-muted/30'
              }`}
            >
              <div className="text-sm font-semibold text-foreground">Relaxed Practice Mode</div>
              <p className="mt-1 text-xs text-muted-foreground">
                Self-paced learning, flexible section jumping, and no timer pressure.
              </p>
            </button>
          </div>
        </div>

        {/* Keyboard Shortcuts */}
        <div className="space-y-3 rounded-2xl border bg-card p-5 shadow-xs sm:p-6">
          <div className="flex items-center justify-between gap-4">
            <div className="flex items-start gap-3">
              <Keyboard className="mt-0.5 h-5 w-5 shrink-0 text-primary" />
              <div className="space-y-1">
                <h2 className="text-sm font-semibold text-foreground">CBT Keyboard Shortcuts</h2>
                <p className="text-xs text-muted-foreground">
                  Enable Alt+N (Next), Alt+P (Previous), Alt+F (Flag for review), and Alt+C (Clear selection).
                </p>
              </div>
            </div>

            <button
              type="button"
              role="switch"
              aria-checked={settings?.keyboard_shortcuts}
              onClick={() => handleSave({ keyboard_shortcuts: !settings?.keyboard_shortcuts })}
              disabled={isSaving}
              className={`flex h-7 min-h-[44px] w-12 items-center rounded-full p-1 transition-colors ${
                settings?.keyboard_shortcuts ? 'bg-primary' : 'bg-muted'
              }`}
            >
              <div
                className={`h-5 w-5 transform rounded-full bg-white shadow-md transition-transform ${
                  settings?.keyboard_shortcuts ? 'translate-x-5' : 'translate-x-0'
                }`}
              />
            </button>
          </div>
        </div>

        {/* Cohort Percentile Opt-in */}
        <div className="space-y-3 rounded-2xl border bg-card p-5 shadow-xs sm:p-6">
          <div className="flex items-center justify-between gap-4">
            <div className="flex items-start gap-3">
              <TrendingUp className="mt-0.5 h-5 w-5 shrink-0 text-primary" />
              <div className="space-y-1">
                <h2 className="text-sm font-semibold text-foreground">Anonymous Cohort Percentiles</h2>
                <p className="text-xs text-muted-foreground">
                  Allow your verified exam attempt scores to be included in anonymous batch percentile rankings across
                  Artha students.
                </p>
              </div>
            </div>

            <button
              type="button"
              role="switch"
              aria-checked={settings?.percentile_optin}
              onClick={() => handleSave({ percentile_optin: !settings?.percentile_optin })}
              disabled={isSaving}
              className={`flex h-7 min-h-[44px] w-12 items-center rounded-full p-1 transition-colors ${
                settings?.percentile_optin ? 'bg-primary' : 'bg-muted'
              }`}
            >
              <div
                className={`h-5 w-5 transform rounded-full bg-white shadow-md transition-transform ${
                  settings?.percentile_optin ? 'translate-x-5' : 'translate-x-0'
                }`}
              />
            </button>
          </div>
        </div>

        {/* Save confirmation toast */}
        {saveSuccess && (
          <div className="flex items-center gap-2 rounded-xl border border-emerald-200 bg-emerald-50 p-3 text-xs text-emerald-800">
            <CheckCircle2 className="h-4 w-4 text-emerald-600" />
            <span>Settings updated successfully.</span>
          </div>
        )}
      </div>
    </div>
  )
}
