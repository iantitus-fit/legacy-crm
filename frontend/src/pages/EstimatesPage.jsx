import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Calculator, Plus } from 'lucide-react'
import { listEstimates, createEstimate } from '../api/estimates'
import { useToast } from '../context/ToastContext'
import SearchInput from '../components/SearchInput'
import Pagination from '../components/Pagination'
import EmptyState from '../components/EmptyState'
import LoadingSpinner from '../components/LoadingSpinner'
import JobPickerModal from '../components/JobPickerModal'

const formatCurrency = (value) => {
  if (!value) return '—'
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    minimumFractionDigits: 2,
  }).format(value)
}

export default function EstimatesPage() {
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
    listEstimates({ search, page, perPage })
      .then((data) => {
        setEstimates(data.items)
        setTotal(data.total)
      })
      .catch(() => addToast('Failed to load estimates', 'error'))
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
        <h1 className="text-2xl font-bold text-th-text">Estimates</h1>
        {createButton}
      </div>

      {/* Search */}
      <div className="mb-4 max-w-sm">
        <SearchInput
          value={search}
          onChange={handleSearch}
          placeholder="Search by name, contact, or address..."
        />
      </div>

      {/* Table */}
      {loading ? (
        <div className="flex justify-center py-16">
          <LoadingSpinner />
        </div>
      ) : estimates.length === 0 ? (
        <EmptyState
          icon={Calculator}
          title={search ? 'No estimates found' : 'No estimates yet'}
          description={
            search
              ? 'Try a different search term'
              : 'Pick a job to create your first estimate'
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
                    Name
                  </th>
                  <th className="text-left text-xs font-medium text-th-text-muted uppercase tracking-wider px-4 py-3">
                    Job / Contact
                  </th>
                  <th className="text-center text-xs font-medium text-th-text-muted uppercase tracking-wider px-4 py-3">
                    Items
                  </th>
                  <th className="text-right text-xs font-medium text-th-text-muted uppercase tracking-wider px-4 py-3">
                    Total
                  </th>
                  <th className="text-right text-xs font-medium text-th-text-muted uppercase tracking-wider px-4 py-3">
                    Created
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
                    <td className="px-4 py-3 text-sm text-th-text-secondary">
                      {est.job_address || est.contact_name || '—'}
                      {est.job_address && est.contact_name && (
                        <span className="text-th-text-muted ml-1">
                          ({est.contact_name})
                        </span>
                      )}
                    </td>
                    <td className="px-4 py-3 text-sm text-th-text-secondary text-center">
                      {est.line_items?.length || 0}
                    </td>
                    <td className="px-4 py-3 text-sm text-right font-mono text-brand-purple">
                      {formatCurrency(est.total)}
                    </td>
                    <td className="px-4 py-3 text-sm text-right text-th-text-muted font-mono">
                      {new Date(est.created_at).toLocaleDateString()}
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
