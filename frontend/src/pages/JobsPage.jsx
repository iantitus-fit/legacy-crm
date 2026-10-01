import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Briefcase, Plus } from 'lucide-react'
import { createEstimate, listEstimates } from '../api/estimates'
import { useToast } from '../context/ToastContext'
import SearchInput from '../components/SearchInput'
import Pagination from '../components/Pagination'
import EmptyState from '../components/EmptyState'
import LoadingSpinner from '../components/LoadingSpinner'
import JobPickerModal from '../components/JobPickerModal'

const JOB_STATUSES = 'approved,in_progress,complete,closed'

const STATUS_BADGE = {
  approved: 'bg-emerald-500/20 text-emerald-400',
  in_progress: 'bg-blue-500/20 text-blue-400',
  complete: 'bg-purple-500/20 text-purple-400',
  closed: 'bg-gray-500/20 text-gray-400',
}

const formatCurrency = (value) => {
  if (!value && value !== 0) return '—'
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(value)
}

const formatDate = (iso) => {
  if (!iso) return '—'
  return new Date(`${iso}T00:00:00`).toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  })
}

export default function JobsPage() {
  const [estimates, setEstimates] = useState([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [search, setSearch] = useState('')
  const [loading, setLoading] = useState(true)
  const [showJobPicker, setShowJobPicker] = useState(false)
  const navigate = useNavigate()
  const { addToast } = useToast()
  const perPage = 25

  const fetchEstimates = () => {
    setLoading(true)
    listEstimates({ search, status: JOB_STATUSES, page, perPage })
      .then((data) => {
        setEstimates(data.items)
        setTotal(data.total)
      })
      .catch(() => addToast('Failed to load jobs', 'error'))
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    fetchEstimates()
  }, [search, page])

  const handleSearch = (value) => {
    setSearch(value)
    setPage(1)
  }

  const handleJobPicked = async (jobId) => {
    setShowJobPicker(false)
    try {
      const est = await createEstimate({ job_id: jobId, name: '' })
      addToast('Estimate created')
      navigate(`/estimates/${est.id}`)
    } catch (err) {
      addToast(err?.response?.data?.detail || 'Failed to create estimate', 'error')
    }
  }

  const createButton = (
    <button
      onClick={() => setShowJobPicker(true)}
      className="flex items-center gap-2 bg-btn-primary-bg hover:bg-btn-primary-hover text-btn-primary-text font-semibold px-4 py-2 rounded-lg text-sm transition-colors"
    >
      <Plus size={16} />
      Create Estimate
    </button>
  )

  return (
    <div>
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-th-text">Jobs</h1>
        {createButton}
      </div>

      {/* Search */}
      <div className="mb-4 max-w-sm">
        <SearchInput
          value={search}
          onChange={handleSearch}
          placeholder="Search by estimate name, client, or address..."
        />
      </div>

      {/* Table */}
      {loading ? (
        <LoadingSpinner centered />
      ) : estimates.length === 0 ? (
        <EmptyState
          icon={Briefcase}
          title={search ? 'No jobs found' : 'No jobs yet'}
          description={
            search
              ? 'Try a different search term'
              : 'Jobs appear here once an estimate is approved. Create an estimate for a client to get started.'
          }
          action={!search ? createButton : null}
        />
      ) : (
        <>
          <div className="bg-surface rounded-xl overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b border-th-border">
                  <th className="text-left text-xs font-medium text-th-text-muted uppercase tracking-wider px-4 py-3">
                    Estimate
                  </th>
                  <th className="text-left text-xs font-medium text-th-text-muted uppercase tracking-wider px-4 py-3">
                    Client
                  </th>
                  <th className="text-left text-xs font-medium text-th-text-muted uppercase tracking-wider px-4 py-3">
                    Type
                  </th>
                  <th className="text-left text-xs font-medium text-th-text-muted uppercase tracking-wider px-4 py-3">
                    Crew
                  </th>
                  <th className="text-left text-xs font-medium text-th-text-muted uppercase tracking-wider px-4 py-3">
                    Scheduled
                  </th>
                  <th className="text-left text-xs font-medium text-th-text-muted uppercase tracking-wider px-4 py-3">
                    Status
                  </th>
                  <th className="text-right text-xs font-medium text-th-text-muted uppercase tracking-wider px-4 py-3">
                    Total
                  </th>
                </tr>
              </thead>
              <tbody>
                {estimates.map((est) => (
                  <tr
                    key={est.id}
                    onClick={() => navigate(`/estimates/${est.id}`)}
                    className="border-b border-th-border/50 last:border-0 hover:bg-surface-hover/50 cursor-pointer transition-colors"
                  >
                    <td className="px-4 py-3 text-sm font-medium text-th-text">
                      {est.name || `Estimate #${est.id}`}
                    </td>
                    <td className="px-4 py-3 text-sm text-th-text">
                      {est.contact_name || '—'}
                      {est.contact_company && (
                        <span className="text-th-text-muted ml-1">({est.contact_company})</span>
                      )}
                    </td>
                    <td className="px-4 py-3 text-sm text-th-text-secondary capitalize">
                      {est.job_type || '—'}
                    </td>
                    <td className="px-4 py-3 text-sm text-th-text-secondary">
                      {est.crew_name ? (
                        <span className="inline-flex items-center gap-1.5">
                          <span
                            className="w-2 h-2 rounded-full"
                            style={{ backgroundColor: est.crew_color || '#6B7280' }}
                          />
                          {est.crew_name}
                        </span>
                      ) : (
                        '—'
                      )}
                    </td>
                    <td className="px-4 py-3 text-xs text-th-text-secondary font-mono">
                      {formatDate(est.scheduled_start)}
                    </td>
                    <td className="px-4 py-3">
                      <span
                        className={`inline-flex items-center px-2 py-0.5 rounded text-[11px] font-medium ${
                          STATUS_BADGE[est.status] || 'bg-gray-500/20 text-gray-400'
                        }`}
                      >
                        {(est.status || '').replace('_', ' ')}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-sm text-right font-mono text-brand-purple">
                      {formatCurrency(est.total)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <Pagination
            page={page}
            perPage={perPage}
            total={total}
            onPageChange={setPage}
          />
        </>
      )}

      {showJobPicker && (
        <JobPickerModal
          title="Select a Job for the New Estimate"
          onClose={() => setShowJobPicker(false)}
          onPick={handleJobPicked}
        />
      )}
    </div>
  )
}
