import React from 'react'

interface ReadingBannerProps {
  onStartWriting: () => void
  className?: string
}

export const ReadingBanner: React.FC<ReadingBannerProps> = ({ onStartWriting, className = '' }) => {
  return (
    <div
      className={`flex items-center justify-between gap-4 rounded-xl border border-amber-200 bg-amber-50 p-4 text-amber-900 dark:border-amber-800 dark:bg-amber-950/40 dark:text-amber-200 ${className}`}
      role="status"
    >
      <div className="flex items-center gap-3">
        <svg
          className="h-5 w-5 shrink-0 text-amber-600 dark:text-amber-400"
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
          />
        </svg>
        <div className="text-sm">
          <span className="font-semibold">Reading Phase: </span>
          You may read questions and review instructions. Answering options will unlock when the writing phase starts.
        </div>
      </div>

      <button
        type="button"
        onClick={onStartWriting}
        className="min-h-[44px] shrink-0 rounded-lg bg-amber-600 px-4 py-2 text-xs font-medium text-white transition-colors hover:bg-amber-700"
      >
        Start Writing Now
      </button>
    </div>
  )
}
