import { Link, useNavigate } from 'react-router-dom'
import { Receipt } from 'lucide-react'

const formatCurrency = (value) => {
  const n = Number(value || 0)
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    minimumFractionDigits: 2,
  }).format(n)
}

const formatDueDate = (iso) => {
  if (!iso) return '—'
  return new Date(`${iso}T00:00:00`).toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  })
}

const isPastDue = (iso) => {
  if (!iso) return false
  const d = new Date(`${iso}T00:00:00`)
  const today = new Date()
  today.setHours(0, 0, 0, 0)
  return d < today
}

/**
 * Dashboard widget showing open invoices (balance_due > 0) with a max
 * of 5 rows. Clicking a row navigates to the invoice detail page.
 */
export default function DashboardInvoicesSection({ invoices = [] }) {
  const navigate = useNavigate()

  return (
    <div className="bg-surface rounded-xl p-4 mb-8">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <Receipt size={16} className="text-brand-purple-text" />
          <h3 className="text-sm font-semibold text-th-text">Open Invoices</h3>
          <span className="text-xs font-mono px-2 py-0.5 rounded-full bg-surface-hover text-brand-purple-text">
            {invoices.length}
          </span>
        </div>
        <Link
          to="/invoices"
          className="text-xs text-brand-purple hover:text-brand-purple-text transition-colors"
        >
          View all →
        </Link>
      </div>

      {invoices.length === 0 ? (
        <p className="text-xs text-th-text-muted py-4 text-center">
          No open invoices
        </p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="border-b border-th-border text-[11px] text-th-text-muted uppercase tracking-wider">
                <th className="text-left px-2 py-2 font-medium">Invoice</th>
                <th className="text-left px-2 py-2 font-medium">Customer</th>
                <th className="text-right px-2 py-2 font-medium">Total</th>
                <th className="text-right px-2 py-2 font-medium">Balance</th>
                <th className="text-right px-2 py-2 font-medium">Due</th>
              </tr>
            </thead>
            <tbody>
              {invoices.slice(0, 5).map((inv) => {
                const overdue = isPastDue(inv.due_date)
                return (
                  <tr
                    key={inv.id}
                    onClick={() => navigate(`/invoices/${inv.id}`)}
                    className="border-b border-th-border/50 last:border-0 hover:bg-surface-hover/50 cursor-pointer transition-colors"
                  >
                    <td className="px-2 py-2 text-sm font-mono text-th-text">
                      {inv.invoice_number}
                    </td>
                    <td className="px-2 py-2 text-sm text-th-text truncate max-w-[10rem]">
                      {inv.contact_name || '—'}
                    </td>
                    <td className="px-2 py-2 text-sm text-right font-mono text-th-text-secondary">
                      {formatCurrency(inv.total)}
                    </td>
                    <td className="px-2 py-2 text-sm text-right font-mono text-brand-purple">
                      {formatCurrency(inv.balance)}
                    </td>
                    <td
                      className={`px-2 py-2 text-xs text-right font-mono ${
                        overdue ? 'text-red-400' : 'text-th-text-muted'
                      }`}
                    >
                      {formatDueDate(inv.due_date)}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
