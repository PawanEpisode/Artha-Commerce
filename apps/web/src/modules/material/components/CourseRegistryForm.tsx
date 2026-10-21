import { CheckCircle2, Download, Shield, Trash2 } from '@artha/design-system'
import React, { useState } from 'react'

import { useRegistry } from '../hooks/useRegistry'
import { ProviderPicker } from './ProviderPicker'

export const CourseRegistryForm: React.FC = () => {
  const { providers, followed, isLoading, follow, unfollow } = useRegistry()
  const [isExporting, setIsExporting] = useState(false)
  const [exportSuccess, setExportSuccess] = useState(false)
  const [isDeleting, setIsDeleting] = useState(false)

  const handleExportData = async () => {
    setIsExporting(true)
    try {
      const response = await fetch('/api/v1/material/me/export/', {
        headers: { 'Content-Type': 'application/json' },
      })
      if (!response.ok) throw new Error('Export failed')
      const blob = await response.blob()
      const url = window.URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `artha-material-progress-${new Date().toISOString().slice(0, 10)}.json`
      a.click()
      window.URL.revokeObjectURL(url)
      setExportSuccess(true)
      setTimeout(() => setExportSuccess(false), 3000)
    } catch (err) {
      console.error(err)
      alert('Failed to export study material data.')
    } finally {
      setIsExporting(false)
    }
  }

  const handleDeleteData = async () => {
    if (
      !window.confirm(
        'Are you sure you want to delete all your study material progress and notes? This action cannot be undone under DPDP rights.',
      )
    ) {
      return
    }

    setIsDeleting(true)
    try {
      const response = await fetch('/api/v1/material/me/data/', {
        method: 'DELETE',
      })
      if (!response.ok) throw new Error('Deletion failed')
      alert('Your study material progress has been permanently erased.')
      window.location.reload()
    } catch (err) {
      console.error(err)
      alert('Failed to erase data.')
    } finally {
      setIsDeleting(false)
    }
  }

  if (isLoading) {
    return (
      <div className="animate-pulse space-y-4">
        <div className="h-32 rounded-2xl bg-muted/30" />
        <div className="h-48 rounded-2xl bg-muted/30" />
      </div>
    )
  }

  return (
    <div className="space-y-8">
      {/* Followed Providers */}
      <ProviderPicker providers={providers} followed={followed} onFollow={follow} onUnfollow={unfollow} />

      {/* DPDP Compliance & Privacy Controls */}
      <div className="space-y-4 rounded-2xl border bg-card p-5 shadow-xs sm:p-6">
        <div className="flex items-center gap-2">
          <Shield className="h-5 w-5 text-primary" />
          <h3 className="text-sm font-bold text-foreground">Data Protection & Student Rights (DPDP Act 2023)</h3>
        </div>
        <p className="text-xs leading-relaxed text-muted-foreground">
          You own your learning progress, notes, and study records. You can download a complete portable copy of your
          study material checklist data at any time or permanently erase it from our servers.
        </p>

        <div className="flex flex-wrap items-center gap-3 pt-2">
          <button
            type="button"
            onClick={handleExportData}
            disabled={isExporting}
            className="inline-flex min-h-[44px] items-center gap-2 rounded-xl border px-4 py-2 text-xs font-semibold hover:bg-muted/60"
          >
            <Download className="h-4 w-4" />
            <span>{isExporting ? 'Exporting...' : 'Export Progress JSON'}</span>
          </button>

          {exportSuccess && (
            <span className="inline-flex items-center gap-1 text-xs font-medium text-emerald-600">
              <CheckCircle2 className="h-4 w-4" /> Export downloaded!
            </span>
          )}

          <button
            type="button"
            onClick={handleDeleteData}
            disabled={isDeleting}
            className="ml-auto inline-flex min-h-[44px] items-center gap-2 rounded-xl border border-rose-200 px-4 py-2 text-xs font-semibold text-rose-600 hover:bg-rose-50"
          >
            <Trash2 className="h-4 w-4" />
            <span>{isDeleting ? 'Erasing...' : 'Erase Material Progress'}</span>
          </button>
        </div>
      </div>
    </div>
  )
}
