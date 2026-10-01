import { useEffect, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { ChevronLeft, ChevronRight, Search } from 'lucide-react'
import { listInvoices } from '../api/invoices'
import { useToast } from '../context/ToastContext'
import LoadingSpinner from '../components/LoadingSpinner'

const STATUS_BADGES = {
  draft: { label: 'Draft', bg: 'bg-gray-500/20', text: 'text-gray-400' },
  sent: { label: 'Sent', bg: 'bg-blue-500/20', text: 'text-blue-400' },
  partial: { label: 'Partially Paid', bg: 'bg-amber-500/20', text: 'text-amber-400' },
  paid: { label: 'Paid', bg: 'bg-green-500/20', text: 'text-green-400' },
  void: { label: 'Void', bg: 'bg-red-500/20', text: 'text-red-400' },
}

const formatCurrency = (value) => {
  if (!value && value !== 0) return '$0.00'
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    minimumFractionDigits: 2,
  }).format(value)
}

export default function InvoiceListPage() {
  const navigate = useNavigate()
  const [searchParams, setSearchParams] = useSearchParams()
  const { addToast } = useToast()

  const [invoices, setInvoices] = useState([])
  const [loading, setLoading] = useState(true)
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [search, setSearch] = useState(searchParams.get('search') || '')
  const [statusFilter, setStatusFilter] = useState(searchParams.get('status') || '')

  const perPage = 25

  useEffect(() => {
    loadInvoices()
  }, [page, statusFilter])

  const loadInvoices = async () => {
    setLoading(true)
    try {
      const data = await listInvoices({ search, status: statusFilter || undefined, page, perPage })
      setInvoices(data.items)
      setTotal(data.total)
    } catch {
      addToast('Failed to load invoices', 'error')
    } finally {
      setLoading(false)
    }
  }

  const handleSearch = (e) => {
    e.preventDefault()
    setPage(1)
    loadInvoices()
  }

  const totalPages = Math.ceil(total / perPage)

  if (loading && invoices.length === 0) return <LoadingSpinner />

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-th-text">Invoices</h1>
      </div>

      {/* Search + Filter */}
      <div className="flex items-center gap-4">
        <form onSubmit={handleSearch} className="flex-1 max-w-md">
          <div className="relative">
            <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-th-text-muted" />
            <input
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search invoices..."
              className="w-full pl-9 pr-3 py-2 bg-surface border border-th-border rounded-lg text-sm text-th-text placeholder-gray-500 focus:outline-none focus:border-th-border-focus"
            />
          </div>
        </form>

        <select
          value={statusFilter}
          onChange={(e) => { setStatusFilter(e.target.value); setPage(1) }}
          className="bg-surface border border-th-border rounded-lg px-3 py-2 text-sm text-th-text focus:outline-none focus:border-th-border-focus"
        >
          <option value="">All Statuses</option>
          <option value="draft">Draft</option>
          <option value="sent">Sent</option>
          <option value="partial">Partial</option>
          <option value="paid">Paid</option>
          <option value="void">Void</option>
        </select>
      </div>

      {/* Table */}
      <div className="bg-surface rounded-xl overflow-hidden">
        <table className="w-full">
          <thead>
            <tr className="border-b border-th-border">
              <th className="text-left px-4 py-3 text-xs font-medium text-th-text-muted uppercase tracking-wider">Invoice #</th>
              <th className="text-left px-4 py-3 text-xs font-medium text-th-text-muted uppercase tracking-wider">Contact</th>
              <th className="text-left px-4 py-3 text-xs font-medium text-th-text-muted uppercase tracking-wider">Job Address</th>
              <th className="text-left px-4 py-3 text-xs font-medium text-th-text-muted uppercase tracking-wider">Status</th>
              <th className="text-left px-4 py-3 text-xs font-medium text-th-text-muted uppercase tracking-wider">Date</th>
              <th className="text-left px-4 py-3 text-xs font-medium text-th-text-muted uppercase tracking-wider">Due Date</th>
              <th className="text-right px-4 py-3 text-xs font-medium text-th-text-muted uppercase tracking-wider">Total</th>
              <th className="text-right px-4 py-3 text-xs font-medium text-th-text-muted uppercase tracking-wider">Balance</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-th-border/50">
            {invoices.length === 0 ? (
              <tr>
                <td colSpan={8} className="px-4 py-8 text-center text-th-text-muted text-sm">
                  No invoices found
                </td>
              </tr>
            ) : (
              invoices.map((inv) => {
                const badge = STATUS_BADGES[inv.status] || STATUS_BADGES.draft
                return (
                  <tr
                    key={inv.id}
                    onClick={() => navigate(`/invoices/${inv.id}`)}
                    className="hover:bg-surface-hover/30 cursor-pointer transition-colors"
                  >
                    <td className="px-4 py-3 text-sm font-medium text-brand-purple">{inv.invoice_number}</td>
                    <td className="px-4 py-3 text-sm text-th-text">{inv.contact_name || '—'}</td>
                    <td className="px-4 py-3 text-sm text-th-text-secondary truncate max-w-[200px]">{inv.job_address || '—'}</td>
                    <td className="px-4 py-3">
                      <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium ${badge.bg} ${badge.text}`}>
                        {badge.label}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-sm text-th-text-secondary">{inv.date_invoiced || '—'}</td>
                    <td className="px-4 py-3 text-sm text-th-text-secondary">{inv.due_date || '—'}</td>
                    <td className="px-4 py-3 text-sm text-th-text text-right font-mono">{formatCurrency(inv.total)}</td>
                    <td className="px-4 py-3 text-sm text-right font-mono">
                      <span className={parseFloat(inv.balance) > 0 ? 'text-brand-purple-text' : 'text-green-400'}>
                        {formatCurrency(inv.balance)}
                      </span>
                    </td>
                  </tr>
                )
              })
            )}
          </tbody>
        </table>
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between">
          <p className="text-sm text-th-text-muted">
            Showing {(page - 1) * perPage + 1}–{Math.min(page * perPage, total)} of {total}
          </p>
          <div className="flex items-center gap-2">
            <button
              onClick={() => setPage(Math.max(1, page - 1))}
              disabled={page === 1}
              className="p-1.5 text-th-text-secondary hover:text-th-text disabled:opacity-30 disabled:cursor-not-allowed"
            >
              <ChevronLeft size={18} />
            </button>
            <span className="text-sm text-th-text-secondary">
              Page {page} of {totalPages}
            </span>
            <button
              onClick={() => setPage(Math.min(totalPages, page + 1))}
              disabled={page === totalPages}
              className="p-1.5 text-th-text-secondary hover:text-th-text disabled:opacity-30 disabled:cursor-not-allowed"
            >
              <ChevronRight size={18} />
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
