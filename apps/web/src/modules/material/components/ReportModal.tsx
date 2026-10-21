import { AlertTriangle, X } from '@artha/design-system'
import React, { useState } from 'react'

import type { MaterialReportPayload } from '../lib/types'

interface ReportModalProps {
  itemId: string
  itemLabel: string
  isOpen: boolean
  onClose: () => void
  onSubmit: (payload: MaterialReportPayload) => Promise<void>
}

export const ReportModal: React.FC<ReportModalProps> = ({ itemId, itemLabel, isOpen, onClose, onSubmit }) => {
  const [reportType, setReportType] = useState<MaterialReportPayload['report_type']>('broken_link')
  const [description, setDescription] = useState('')
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [isSuccess, setIsSuccess] = useState(false)
  const [error, setError] = useState<string | null>(null)

  if (!isOpen) return null

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setIsSubmitting(true)
    setError(null)

    try {
      await onSubmit({
        item_id: itemId,
        report_type: reportType,
        description,
      })
      setIsSuccess(true)
      setTimeout(() => {
        setIsSuccess(false)
        setDescription('')
        onClose()
      }, 1500)
    } catch {
      setError('Failed to submit report. Please try again.')
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4 backdrop-blur-xs"
      role="dialog"
      aria-modal="true"
      aria-labelledby="report-modal-title"
    >
      <div className="w-full max-w-md space-y-4 rounded-2xl border bg-card p-6 shadow-xl">
        <div className="flex items-center justify-between border-b pb-3">
          <div className="flex items-center gap-2 font-semibold text-foreground">
            <AlertTriangle className="h-5 w-5 text-amber-500" />
            <h2 id="report-modal-title" className="text-base">
              Report Issue for {itemLabel}
            </h2>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg p-1 text-muted-foreground hover:bg-muted hover:text-foreground"
            aria-label="Close dialog"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {isSuccess ? (
          <div className="rounded-xl bg-emerald-50 p-4 text-center text-sm font-medium text-emerald-800">
            Thank you! Your report has been submitted to the Artha curation team.
          </div>
        ) : (
          <form onSubmit={handleSubmit} className="space-y-4">
            {error && (
              <div className="rounded-xl border border-rose-200 bg-rose-50 p-3 text-xs text-rose-700">{error}</div>
            )}

            <div className="space-y-1.5">
              <label htmlFor="report-type" className="text-xs font-semibold text-foreground">
                Issue Type
              </label>
              <select
                id="report-type"
                value={reportType}
                onChange={(e) => setReportType(e.target.value as MaterialReportPayload['report_type'])}
                className="min-h-[44px] w-full rounded-xl border bg-background px-3 py-2 text-sm focus:ring-2 focus:ring-primary focus:outline-hidden"
              >
                <option value="broken_link">Broken PDF Link / Offset Page Mismatch</option>
                <option value="wrong_mapping">Wrong Chapter or Topic Association</option>
                <option value="typo">Content Typo / Missing Figures</option>
                <option value="missing_content">Omitted Problem or Solution Sub-part</option>
                <option value="other">Other Inquiry</option>
              </select>
            </div>

            <div className="space-y-1.5">
              <label htmlFor="report-desc" className="text-xs font-semibold text-foreground">
                Details
              </label>
              <textarea
                id="report-desc"
                rows={3}
                required
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder="Describe what is wrong or provide the correct official page number..."
                className="w-full resize-none rounded-xl border bg-background px-3 py-2 text-sm focus:ring-2 focus:ring-primary focus:outline-hidden"
              />
            </div>

            <div className="flex items-center justify-end gap-2 pt-2">
              <button
                type="button"
                onClick={onClose}
                className="min-h-[44px] rounded-xl border px-4 py-2 text-sm font-medium hover:bg-muted"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={isSubmitting || !description.trim()}
                className="min-h-[44px] rounded-xl bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:opacity-90 disabled:opacity-50"
              >
                {isSubmitting ? 'Submitting...' : 'Submit Report'}
              </button>
            </div>
          </form>
        )}
      </div>
    </div>
  )
}
