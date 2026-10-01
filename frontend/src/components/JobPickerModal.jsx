import { useEffect, useState } from 'react'
import { X, Search, Loader2 } from 'lucide-react'
import { listJobs } from '../api/jobs'

/**
 * Reusable job picker modal with debounced search. When the user selects
 * a job, calls `onPick(jobId)` and the parent is responsible for closing
 * and reacting (e.g. creating an estimate).
 *
 * Props:
 * - onClose: () => void
 * - onPick: (jobId: number, job: object) => void
 * - title: header text (default "Select a Job")
 */
export default function JobPickerModal({ onClose, onPick, title = 'Select a Job', contactId }) {
  const [query, setQuery] = useState('')
  const [results, setResults] = useState([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  // Load an initial list of recent jobs and debounce subsequent searches
  useEffect(() => {
    const handle = setTimeout(async () => {
      setLoading(true)
      setError(null)
      try {
        const data = await listJobs({
          search: query.trim() || undefined,
          contactId,
          perPage: 20,
        })
        setResults(data.items || [])
      } catch (err) {
        setError('Failed to load jobs')
        setResults([])
      } finally {
        setLoading(false)
      }
    }, 250)
    return () => clearTimeout(handle)
  }, [query, contactId])

  return (
    <div
      className="fixed inset-0 bg-black/60 flex items-start justify-center z-50 pt-20 px-4"
      onClick={onClose}
    >
      <div
        className="bg-surface border border-th-border rounded-lg w-full max-w-2xl max-h-[70vh] flex flex-col"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between p-4 border-b border-th-border">
          <h2 className="text-lg font-semibold text-th-text">{title}</h2>
          <button
            onClick={onClose}
            className="text-slate-400 hover:text-th-text"
            aria-label="Close"
          >
            <X size={20} />
          </button>
        </div>

        <div className="p-4 border-b border-th-border">
          <div className="relative">
            <Search
              size={16}
              className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400"
            />
            <input
              type="text"
              autoFocus
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Escape') onClose()
              }}
              placeholder="Search by address or contact name..."
              className="w-full pl-9 pr-3 py-2 bg-page border border-th-border rounded text-th-text placeholder-slate-500 focus:outline-none focus:border-th-border-focus"
            />
          </div>
        </div>

        <div className="flex-1 overflow-y-auto">
          {loading && (
            <div className="flex items-center justify-center py-8 text-slate-400">
              <Loader2 className="animate-spin mr-2" size={16} />
              Loading...
            </div>
          )}
          {error && <div className="p-4 text-red-400 text-sm">{error}</div>}
          {!loading && !error && results.length === 0 && (
            <div className="p-4 text-slate-400 text-sm">No jobs found.</div>
          )}
          {!loading && results.length > 0 && (
            <ul className="divide-y divide-slate-700">
              {results.map((job) => {
                const displayName =
                  job.display_name || job.property_address || `Job #${job.id}`
                return (
                  <li key={job.id}>
                    <button
                      type="button"
                      onClick={() => onPick(job.id, job)}
                      className="w-full text-left px-4 py-3 hover:bg-page transition-colors"
                    >
                      <div className="text-sm text-th-text truncate">{displayName}</div>
                      <div className="text-xs text-slate-400 mt-0.5 flex items-center gap-2">
                        {job.contact_name && <span>{job.contact_name}</span>}
                        {job.work_type && (
                          <span className="text-slate-500">· {job.work_type}</span>
                        )}
                      </div>
                    </button>
                  </li>
                )
              })}
            </ul>
          )}
        </div>
      </div>
    </div>
  )
}
