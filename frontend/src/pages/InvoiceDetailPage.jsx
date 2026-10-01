import { useEffect, useState } from 'react'
import { useParams, useNavigate, Link } from 'react-router-dom'
import {
  DollarSign,
  Download,
  Loader2,
  Mail,
  Pencil,
  Plus,
  Trash2,
  X,
  XCircle,
} from 'lucide-react'
import {
  getInvoice,
  updateInvoice,
  addInvoiceItem,
  updateInvoiceItem,
  deleteInvoiceItem,
  sendInvoice,
  listPayments,
  recordPayment,
  deletePayment,
  sendReceipt,
} from '../api/invoices'
import { useToast } from '../context/ToastContext'
import ConfirmDialog from '../components/ConfirmDialog'
import LoadingSpinner from '../components/LoadingSpinner'
import BackButton from '../components/BackButton'
import AddressLink from '../components/AddressLink'

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

function InvoiceItemEditModal({ open, item, onSave, onClose }) {
  const [description, setDescription] = useState('')
  const [qty, setQty] = useState('')
  const [unitPrice, setUnitPrice] = useState('')
  const [body, setBody] = useState('')
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    if (item && open) {
      setDescription(item.description || '')
      setQty(item.qty ?? '')
      setUnitPrice(item.unit_price ?? '')
      setBody(item.body || '')
    }
  }, [item, open])

  const handleSave = async () => {
    setSaving(true)
    try {
      await onSave(item?.id, {
        description,
        qty: parseFloat(qty) || 0,
        unit_price: parseFloat(unitPrice) || 0,
        body: body || null,
      })
      onClose()
    } finally {
      setSaving(false)
    }
  }

  if (!open) return null

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div className="bg-surface rounded-xl border border-th-border p-6 w-full max-w-lg">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold text-th-text">
            {item?.id ? 'Edit Item' : 'Add Item'}
          </h2>
          <button onClick={onClose} className="text-th-text-muted hover:text-th-text">
            <X size={20} />
          </button>
        </div>

        <div className="space-y-4">
          <div>
            <label className="block text-xs text-th-text-muted mb-1">Description</label>
            <input
              type="text"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              className="w-full bg-page border border-th-border rounded-lg px-3 py-2 text-sm text-th-text focus:outline-none focus:border-th-border-focus"
              autoFocus
            />
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-xs text-th-text-muted mb-1">Quantity</label>
              <input
                type="number"
                step="0.01"
                value={qty}
                onChange={(e) => setQty(e.target.value)}
                className="w-full bg-page border border-th-border rounded-lg px-3 py-2 text-sm text-th-text font-mono text-right focus:outline-none focus:border-th-border-focus"
              />
            </div>
            <div>
              <label className="block text-xs text-th-text-muted mb-1">Unit Price</label>
              <input
                type="number"
                step="0.01"
                value={unitPrice}
                onChange={(e) => setUnitPrice(e.target.value)}
                className="w-full bg-page border border-th-border rounded-lg px-3 py-2 text-sm text-th-text font-mono text-right focus:outline-none focus:border-th-border-focus"
              />
            </div>
          </div>

          <div>
            <label className="block text-xs text-th-text-muted mb-1">Body (optional)</label>
            <textarea
              rows={3}
              value={body}
              onChange={(e) => setBody(e.target.value)}
              className="w-full bg-page border border-th-border rounded-lg px-3 py-2 text-sm text-th-text-secondary focus:outline-none focus:border-th-border-focus resize-y"
            />
          </div>
        </div>

        <div className="flex justify-end gap-3 mt-4 pt-4 border-t border-th-border">
          <button
            onClick={onClose}
            className="px-4 py-2 text-sm text-th-text-secondary hover:text-th-text transition-colors"
          >
            Cancel
          </button>
          <button
            onClick={handleSave}
            disabled={saving || !description.trim()}
            className="px-4 py-2 text-sm font-medium bg-btn-primary-bg hover:bg-btn-primary-hover disabled:opacity-50 text-btn-primary-text rounded-lg transition-colors"
          >
            {saving ? 'Saving...' : item?.id ? 'Save' : 'Add Item'}
          </button>
        </div>
      </div>
    </div>
  )
}

const PAYMENT_METHODS = [
  { value: 'cash', label: 'Cash' },
  { value: 'check', label: 'Check' },
  { value: 'credit_card', label: 'Credit Card' },
  { value: 'debit_card', label: 'Debit Card' },
  { value: 'ach', label: 'ACH' },
  { value: 'zelle', label: 'Zelle' },
  { value: 'venmo', label: 'Venmo' },
  { value: 'other', label: 'Other' },
]

function ReceivePaymentModal({ invoice, onSave, onClose }) {
  const today = new Date().toISOString().split('T')[0]
  const [dateReceived, setDateReceived] = useState(today)
  const [amount, setAmount] = useState(invoice?.balance ? String(parseFloat(invoice.balance)) : '')
  const [method, setMethod] = useState('')
  const [reference, setReference] = useState('')
  const [noteText, setNoteText] = useState('')
  const [isDeposit, setIsDeposit] = useState(false)
  const [sendReceiptEmail, setSendReceiptEmail] = useState(false)
  const [receiptEmail, setReceiptEmail] = useState(invoice?.contact_email || '')
  const [saving, setSaving] = useState(false)

  const handleSubmit = async (markAsPaid = false) => {
    const payAmount = markAsPaid ? parseFloat(invoice?.balance || 0) : parseFloat(amount)
    if (!payAmount || payAmount <= 0 || !method) return
    setSaving(true)
    try {
      await onSave({
        date_received: dateReceived,
        amount: payAmount,
        method,
        reference: reference || null,
        notes: noteText || null,
        is_deposit: isDeposit,
        send_receipt: sendReceiptEmail && !!receiptEmail,
        receipt_email: receiptEmail || null,
      })
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div className="bg-surface rounded-xl border border-th-border p-6 w-full max-w-lg">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold text-th-text">Receive Payment</h2>
          <button onClick={onClose} className="text-th-text-muted hover:text-th-text">
            <X size={20} />
          </button>
        </div>

        <div className="space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-xs text-th-text-muted mb-1">Date Received</label>
              <input
                type="date"
                value={dateReceived}
                onChange={(e) => setDateReceived(e.target.value)}
                className="w-full bg-page border border-th-border rounded-lg px-3 py-2 text-sm text-th-text focus:outline-none focus:border-th-border-focus"
              />
            </div>
            <div>
              <label className="block text-xs text-th-text-muted mb-1">Amount</label>
              <input
                type="number"
                step="0.01"
                value={amount}
                onChange={(e) => setAmount(e.target.value)}
                className="w-full bg-page border border-th-border rounded-lg px-3 py-2 text-sm text-th-text font-mono text-right focus:outline-none focus:border-th-border-focus"
                autoFocus
              />
            </div>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-xs text-th-text-muted mb-1">Method</label>
              <select
                value={method}
                onChange={(e) => setMethod(e.target.value)}
                className="w-full bg-page border border-th-border rounded-lg px-3 py-2 text-sm text-th-text focus:outline-none focus:border-th-border-focus"
              >
                <option value="">Select method...</option>
                {PAYMENT_METHODS.map((m) => (
                  <option key={m.value} value={m.value}>{m.label}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-xs text-th-text-muted mb-1">Ref Number</label>
              <input
                type="text"
                value={reference}
                onChange={(e) => setReference(e.target.value)}
                placeholder="Check #, txn ID..."
                className="w-full bg-page border border-th-border rounded-lg px-3 py-2 text-sm text-th-text placeholder-gray-600 focus:outline-none focus:border-th-border-focus"
              />
            </div>
          </div>

          <div>
            <label className="block text-xs text-th-text-muted mb-1">Note</label>
            <textarea
              rows={2}
              value={noteText}
              onChange={(e) => setNoteText(e.target.value)}
              className="w-full bg-page border border-th-border rounded-lg px-3 py-2 text-sm text-th-text focus:outline-none focus:border-th-border-focus resize-y"
            />
          </div>

          <label className="flex items-center gap-2 cursor-pointer">
            <input
              type="checkbox"
              checked={isDeposit}
              onChange={(e) => setIsDeposit(e.target.checked)}
              className="rounded border-th-border-secondary bg-page text-brand-purple focus:ring-brand-purple"
            />
            <span className="text-sm text-th-text">Deposit Payment</span>
          </label>

          <div className="border-t border-th-border pt-4">
            <label className="flex items-center gap-2 cursor-pointer mb-2">
              <input
                type="checkbox"
                checked={sendReceiptEmail}
                onChange={(e) => setSendReceiptEmail(e.target.checked)}
                className="rounded border-th-border-secondary bg-page text-brand-purple focus:ring-brand-purple"
              />
              <span className="text-sm text-th-text">Send Email Receipt</span>
            </label>
            {sendReceiptEmail && (
              <input
                type="email"
                value={receiptEmail}
                onChange={(e) => setReceiptEmail(e.target.value)}
                placeholder="customer@example.com"
                className="w-full bg-page border border-th-border rounded-lg px-3 py-2 text-sm text-th-text placeholder-gray-600 focus:outline-none focus:border-th-border-focus"
              />
            )}
          </div>
        </div>

        <div className="flex justify-end gap-3 mt-4 pt-4 border-t border-th-border">
          <button
            onClick={onClose}
            className="px-4 py-2 text-sm text-th-text-secondary hover:text-th-text transition-colors"
          >
            Cancel
          </button>
          {parseFloat(invoice?.balance || 0) > 0 && (
            <button
              onClick={() => handleSubmit(true)}
              disabled={saving || !method}
              className="px-4 py-2 text-sm font-medium bg-green-600 hover:bg-green-700 disabled:opacity-50 text-th-text rounded-lg transition-colors"
            >
              {saving ? 'Saving...' : 'Mark as Paid'}
            </button>
          )}
          <button
            onClick={() => handleSubmit(false)}
            disabled={saving || !method || !parseFloat(amount)}
            className="px-4 py-2 text-sm font-medium bg-btn-primary-bg hover:bg-btn-primary-hover disabled:opacity-50 text-btn-primary-text rounded-lg transition-colors"
          >
            {saving ? 'Saving...' : 'Save'}
          </button>
        </div>
      </div>
    </div>
  )
}

export default function InvoiceDetailPage() {
  const { id } = useParams()
  const navigate = useNavigate()
  const { addToast } = useToast()

  const [invoice, setInvoice] = useState(null)
  const [loading, setLoading] = useState(true)
  const [pdfLoading, setPdfLoading] = useState(false)
  const [editItem, setEditItem] = useState(null)
  const [showAddItem, setShowAddItem] = useState(false)
  const [deleteConfirm, setDeleteConfirm] = useState(null)
  const [notes, setNotes] = useState('')
  const [savingNotes, setSavingNotes] = useState(false)
  const [voidConfirm, setVoidConfirm] = useState(false)

  // Send modal
  const [showSendModal, setShowSendModal] = useState(false)
  const [sendForm, setSendForm] = useState({ to_email: '', subject: '', message: '' })
  const [sendLoading, setSendLoading] = useState(false)

  // Payments
  const [payments, setPayments] = useState([])
  const [showPaymentModal, setShowPaymentModal] = useState(false)
  const [deletePaymentConfirm, setDeletePaymentConfirm] = useState(null)
  const [showReceiptModal, setShowReceiptModal] = useState(null)
  const [receiptForm, setReceiptForm] = useState({ to_email: '', subject: '', message: '' })
  const [receiptLoading, setReceiptLoading] = useState(false)

  useEffect(() => {
    loadInvoice()
  }, [id])

  const loadInvoice = async () => {
    setLoading(true)
    try {
      const data = await getInvoice(id)
      setInvoice(data)
      setNotes(data.notes || '')
      const payData = await listPayments(id)
      setPayments(payData.items || [])
    } catch {
      addToast('Failed to load invoice', 'error')
    } finally {
      setLoading(false)
    }
  }

  const handleSaveNotes = async () => {
    setSavingNotes(true)
    try {
      await updateInvoice(id, { notes })
      addToast('Notes saved')
    } catch {
      addToast('Failed to save notes', 'error')
    } finally {
      setSavingNotes(false)
    }
  }

  const handleUpdateDates = async (field, value) => {
    try {
      const data = await updateInvoice(id, { [field]: value || null })
      setInvoice(data)
    } catch {
      addToast('Failed to update', 'error')
    }
  }

  const handleSaveItem = async (itemId, itemData) => {
    try {
      if (itemId) {
        await updateInvoiceItem(id, itemId, itemData)
      } else {
        await addInvoiceItem(id, itemData)
      }
      await loadInvoice()
      addToast(itemId ? 'Item updated' : 'Item added')
    } catch {
      addToast('Failed to save item', 'error')
    }
  }

  const handleDeleteItem = async (itemId) => {
    try {
      await deleteInvoiceItem(id, itemId)
      await loadInvoice()
      addToast('Item deleted')
    } catch {
      addToast('Failed to delete item', 'error')
    }
    setDeleteConfirm(null)
  }

  const handleDownloadPdf = async () => {
    setPdfLoading(true)
    try {
      const token = localStorage.getItem('access_token')
      const res = await fetch(`/api/invoices/${id}/pdf`, {
        headers: { Authorization: `Bearer ${token}` },
      })
      if (!res.ok) throw new Error('PDF generation failed')
      const blob = await res.blob()
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `Invoice_${invoice?.invoice_number || 'Invoice'}.pdf`
      document.body.appendChild(a)
      a.click()
      a.remove()
      URL.revokeObjectURL(url)
    } catch {
      addToast('Failed to generate PDF', 'error')
    } finally {
      setPdfLoading(false)
    }
  }

  const handleOpenSendModal = () => {
    setSendForm({
      to_email: invoice?.contact_email || '',
      subject: `Invoice ${invoice?.invoice_number} from Legacy Roofing & Exteriors`,
      message: `Please find attached your invoice ${invoice?.invoice_number}.`,
    })
    setShowSendModal(true)
  }

  const handleSendInvoice = async () => {
    if (!sendForm.to_email) {
      addToast('Email address is required', 'error')
      return
    }
    setSendLoading(true)
    try {
      await sendInvoice(id, sendForm)
      addToast(`Invoice sent to ${sendForm.to_email}`)
      setShowSendModal(false)
      await loadInvoice()
    } catch {
      addToast('Failed to send invoice', 'error')
    } finally {
      setSendLoading(false)
    }
  }

  const handleRecordPayment = async (paymentData) => {
    try {
      await recordPayment(id, paymentData)
      addToast('Payment recorded')
      setShowPaymentModal(false)
      await loadInvoice()
    } catch (err) {
      addToast(err?.response?.data?.detail || 'Failed to record payment', 'error')
    }
  }

  const handleDeletePayment = async (paymentId) => {
    try {
      await deletePayment(id, paymentId)
      addToast('Payment deleted')
      await loadInvoice()
    } catch {
      addToast('Failed to delete payment', 'error')
    }
    setDeletePaymentConfirm(null)
  }

  const handleSendReceipt = async () => {
    if (!receiptForm.to_email) return
    setReceiptLoading(true)
    try {
      await sendReceipt(id, showReceiptModal, receiptForm)
      addToast(`Receipt sent to ${receiptForm.to_email}`)
      setShowReceiptModal(null)
    } catch {
      addToast('Failed to send receipt', 'error')
    } finally {
      setReceiptLoading(false)
    }
  }

  const handleVoid = async () => {
    try {
      const data = await updateInvoice(id, { status: 'void' })
      setInvoice(data)
      addToast('Invoice voided')
    } catch {
      addToast('Failed to void invoice', 'error')
    }
    setVoidConfirm(false)
  }

  if (loading) return <LoadingSpinner />
  if (!invoice) return <div className="text-th-text-secondary">Invoice not found</div>

  const badge = STATUS_BADGES[invoice.status] || STATUS_BADGES.draft
  const taxRatePct = invoice.tax_rate ? (parseFloat(invoice.tax_rate) * 100).toFixed(2) : '7.00'

  return (
    <div className="space-y-6">
      <BackButton to="/invoices" label="Back to Invoices" />

      {/* Header */}
      <div className="flex items-start gap-4">
        <div className="flex-1">
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-bold text-th-text">{invoice.invoice_number}</h1>
            <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${badge.bg} ${badge.text}`}>
              {badge.label}
            </span>
          </div>
          <div className="flex items-center gap-4 mt-1 text-sm text-th-text-secondary">
            {invoice.contact_name && <span>{invoice.contact_name}</span>}
            {invoice.job_address && (
              <AddressLink address={invoice.job_address} className="text-th-text-secondary" />
            )}
          </div>
        </div>
      </div>

      {/* Info bar */}
      <div className="flex items-center gap-6 ml-11">
        <div>
          <label className="block text-xs text-th-text-muted mb-1">Date Invoiced</label>
          <input
            type="date"
            value={invoice.date_invoiced || ''}
            onChange={(e) => handleUpdateDates('date_invoiced', e.target.value)}
            className="bg-surface border border-th-border rounded-lg px-3 py-1.5 text-sm text-th-text focus:outline-none focus:border-th-border-focus"
          />
        </div>
        <div>
          <label className="block text-xs text-th-text-muted mb-1">Due Date</label>
          <input
            type="date"
            value={invoice.due_date || ''}
            onChange={(e) => handleUpdateDates('due_date', e.target.value)}
            className="bg-surface border border-th-border rounded-lg px-3 py-1.5 text-sm text-th-text focus:outline-none focus:border-th-border-focus"
          />
        </div>
      </div>

      {/* Action buttons */}
      <div className="flex items-center gap-2 ml-11">
        <button
          onClick={handleDownloadPdf}
          disabled={pdfLoading}
          className="flex items-center gap-1.5 px-3 py-1.5 text-sm text-th-text bg-blue-600 hover:bg-blue-700 disabled:opacity-50 rounded-lg transition-colors"
        >
          {pdfLoading ? <Loader2 size={15} className="animate-spin" /> : <Download size={15} />}
          {pdfLoading ? 'Generating...' : 'Download PDF'}
        </button>
        <button
          onClick={handleOpenSendModal}
          className="flex items-center gap-1.5 px-3 py-1.5 text-sm text-th-text-secondary hover:text-th-text hover:bg-surface rounded-lg transition-colors"
        >
          <Mail size={15} />
          Send Invoice
        </button>
        {invoice.status !== 'paid' && invoice.status !== 'void' && (
          <button
            onClick={() => setVoidConfirm(true)}
            className="flex items-center gap-1.5 px-3 py-1.5 text-sm text-red-400 hover:text-red-300 hover:bg-surface rounded-lg transition-colors"
          >
            <XCircle size={15} />
            Void Invoice
          </button>
        )}
      </div>

      {/* Invoice Items */}
      <div className="bg-surface rounded-xl overflow-hidden ml-11">
        <div className="flex items-center gap-2 px-4 py-2.5 border-b border-th-border text-xs font-medium text-th-text-muted uppercase tracking-wider">
          <div className="flex-1">Description</div>
          <div className="w-20 text-right">Qty</div>
          <div className="w-28 text-right">Unit Price</div>
          <div className="w-28 text-right">Total</div>
          <div className="w-16" />
        </div>

        <div className="divide-y divide-th-border/50">
          {invoice.items.filter((item) => item.source_type !== 'deposit_credit').map((item) => (
            <div key={item.id} className="flex items-center gap-2 px-4 py-2.5 group hover:bg-surface-hover/30 transition-colors">
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <span className="text-sm text-th-text truncate">{item.description || 'Untitled'}</span>
                  {item.source_type === 'change_order' && item.source_co_number && (
                    <span className="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-semibold bg-badge-warning-bg text-brand-purple-text">
                      CO #{item.source_co_number}
                    </span>
                  )}
                </div>
                {item.body && (
                  <span className="text-xs text-th-text-muted block truncate mt-0.5">{item.body}</span>
                )}
              </div>
              <div className="w-20 text-right text-sm font-mono text-th-text">
                {item.qty ? parseFloat(item.qty) : ''}
              </div>
              <div className="w-28 text-right text-sm font-mono text-th-text">
                {item.unit_price ? formatCurrency(item.unit_price) : ''}
              </div>
              <div className="w-28 text-right text-sm font-mono text-th-text">
                {formatCurrency(item.line_total)}
              </div>
              <div className="w-16 flex items-center justify-end gap-1">
                <button
                  onClick={() => setEditItem(item)}
                  className="opacity-0 group-hover:opacity-100 text-th-text-muted hover:text-brand-purple transition-all p-1"
                >
                  <Pencil size={13} />
                </button>
                <button
                  onClick={() => setDeleteConfirm(item.id)}
                  className="opacity-0 group-hover:opacity-100 text-th-text-muted hover:text-red-400 transition-all p-1"
                >
                  <Trash2 size={13} />
                </button>
              </div>
            </div>
          ))}
        </div>

        {/* Add Item */}
        <div className="px-4 py-3 border-t border-th-border">
          <button
            onClick={() => {
              setEditItem({})
              setShowAddItem(true)
            }}
            className="flex items-center gap-1.5 text-sm text-th-text-muted hover:text-brand-purple transition-colors"
          >
            <Plus size={15} />
            Add Item
          </button>
        </div>
      </div>

      {/* Totals */}
      <div className="ml-11 flex justify-end">
        <div className="w-72 bg-surface rounded-xl p-4 space-y-2">
          <div className="flex justify-between text-sm">
            <span className="text-th-text-muted">Subtotal</span>
            <span className="font-mono text-th-text">{formatCurrency(invoice.subtotal)}</span>
          </div>
          <div className="flex justify-between text-sm">
            <span className="text-th-text-muted">Tax ({taxRatePct}%)</span>
            <span className="font-mono text-th-text">{formatCurrency(invoice.tax)}</span>
          </div>
          {invoice.items.filter((item) => item.source_type === 'deposit_credit').map((credit) => (
            <div key={credit.id} className="flex justify-between text-sm">
              <span className="text-th-text-muted">{credit.description}</span>
              <span className="font-mono text-th-text">{formatCurrency(credit.line_total)}</span>
            </div>
          ))}
          <div className="flex justify-between text-sm font-semibold pt-2 border-t border-th-border">
            <span className="text-th-text">Total</span>
            <span className="font-mono text-th-text">{formatCurrency(invoice.total)}</span>
          </div>
          <div className="flex justify-between text-sm">
            <span className="text-th-text-muted">Amount Paid</span>
            <span className="font-mono text-th-text">{formatCurrency(invoice.amount_paid)}</span>
          </div>
          <div className="flex justify-between text-sm font-semibold pt-2 border-t border-th-border">
            <span className="text-brand-purple-text">Balance Due</span>
            <span className={`font-mono ${parseFloat(invoice.balance) > 0 ? 'text-brand-purple-text' : 'text-green-400'}`}>
              {formatCurrency(invoice.balance)}
            </span>
          </div>
        </div>
      </div>

      {/* Payments Section */}
      <div className="ml-11">
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-xs text-th-text-muted uppercase tracking-wider font-medium">Payments</h2>
          {invoice.status !== 'void' && (
            <button
              onClick={() => setShowPaymentModal(true)}
              className="flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium bg-green-600 hover:bg-green-700 text-th-text rounded-lg transition-colors"
            >
              <DollarSign size={15} />
              Receive Payment
            </button>
          )}
        </div>

        <div className="bg-surface rounded-xl overflow-hidden">
          {payments.length === 0 ? (
            <div className="px-4 py-6 text-center text-sm text-th-text-muted">No payments recorded</div>
          ) : (
            <>
              <div className="flex items-center gap-2 px-4 py-2.5 border-b border-th-border text-xs font-medium text-th-text-muted uppercase tracking-wider">
                <div className="w-28">Date</div>
                <div className="w-28 text-right">Amount</div>
                <div className="w-28">Method</div>
                <div className="flex-1">Reference</div>
                <div className="w-20">Type</div>
                <div className="w-16" />
              </div>
              <div className="divide-y divide-th-border/50">
                {payments.map((p) => (
                  <div key={p.id} className="flex items-center gap-2 px-4 py-2.5 group hover:bg-surface-hover/30 transition-colors">
                    <div className="w-28 text-sm text-th-text">{p.date_received}</div>
                    <div className="w-28 text-right text-sm font-mono text-green-400">{formatCurrency(p.amount)}</div>
                    <div className="w-28 text-sm text-th-text capitalize">{(p.method || '').replace('_', ' ')}</div>
                    <div className="flex-1 text-sm text-th-text-secondary truncate">{p.reference || '—'}</div>
                    <div className="w-20">
                      <span className={`inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-semibold ${p.is_deposit ? 'bg-blue-500/20 text-blue-400' : 'bg-gray-500/20 text-th-text-secondary'}`}>
                        {p.is_deposit ? 'Deposit' : 'Payment'}
                      </span>
                    </div>
                    <div className="w-16 flex items-center justify-end gap-1">
                      <button
                        onClick={() => {
                          setReceiptForm({
                            to_email: invoice?.contact_email || '',
                            subject: `Payment Receipt — ${invoice?.invoice_number}`,
                            message: '',
                          })
                          setShowReceiptModal(p.id)
                        }}
                        className="opacity-0 group-hover:opacity-100 text-th-text-muted hover:text-blue-400 transition-all p-1"
                        title="Send Receipt"
                      >
                        <Mail size={13} />
                      </button>
                      <button
                        onClick={() => setDeletePaymentConfirm(p.id)}
                        className="opacity-0 group-hover:opacity-100 text-th-text-muted hover:text-red-400 transition-all p-1"
                        title="Delete Payment"
                      >
                        <Trash2 size={13} />
                      </button>
                    </div>
                  </div>
                ))}
              </div>
              <div className="flex justify-end px-4 py-2.5 border-t border-th-border">
                <span className="text-sm text-th-text-muted mr-4">Total Paid:</span>
                <span className="text-sm font-mono font-semibold text-green-400">
                  {formatCurrency(payments.reduce((sum, p) => sum + parseFloat(p.amount || 0), 0))}
                </span>
              </div>
            </>
          )}
        </div>
      </div>

      {/* Notes */}
      <div className="ml-11">
        <label className="block text-xs text-th-text-muted mb-2 uppercase tracking-wider font-medium">Notes</label>
        <textarea
          rows={3}
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
          placeholder="Internal invoice notes..."
          className="w-full bg-surface border border-th-border rounded-lg px-3 py-2 text-sm text-th-text focus:outline-none focus:border-th-border-focus resize-y"
        />
        <button
          onClick={handleSaveNotes}
          disabled={savingNotes}
          className="mt-2 px-3 py-1.5 text-sm font-medium bg-surface-hover hover:bg-th-border-secondary text-th-text rounded-lg transition-colors disabled:opacity-50"
        >
          {savingNotes ? 'Saving...' : 'Save Notes'}
        </button>
      </div>

      {/* Edit Item Modal */}
      <InvoiceItemEditModal
        open={!!editItem || showAddItem}
        item={editItem}
        onSave={handleSaveItem}
        onClose={() => {
          setEditItem(null)
          setShowAddItem(false)
        }}
      />

      {/* Delete Item Confirm */}
      <ConfirmDialog
        open={!!deleteConfirm}
        title="Delete Item"
        message="Are you sure you want to delete this item?"
        onConfirm={() => handleDeleteItem(deleteConfirm)}
        onCancel={() => setDeleteConfirm(null)}
      />

      {/* Void Confirm */}
      <ConfirmDialog
        open={voidConfirm}
        title="Void Invoice"
        message="Are you sure you want to void this invoice? This action cannot be easily undone."
        onConfirm={handleVoid}
        onCancel={() => setVoidConfirm(false)}
      />

      {/* Delete Payment Confirm */}
      <ConfirmDialog
        open={!!deletePaymentConfirm}
        title="Delete Payment"
        message="Are you sure you want to delete this payment? The invoice balance will be recalculated."
        onConfirm={() => handleDeletePayment(deletePaymentConfirm)}
        onCancel={() => setDeletePaymentConfirm(null)}
      />

      {/* Send Receipt Modal */}
      {showReceiptModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
          <div className="bg-surface rounded-xl border border-th-border p-6 w-full max-w-md">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-lg font-semibold text-th-text">Send Receipt</h2>
              <button onClick={() => setShowReceiptModal(null)} className="text-th-text-muted hover:text-th-text">
                <X size={20} />
              </button>
            </div>
            <div className="space-y-4">
              <div>
                <label className="block text-xs text-th-text-muted mb-1">To Email</label>
                <input
                  type="email"
                  value={receiptForm.to_email}
                  onChange={(e) => setReceiptForm({ ...receiptForm, to_email: e.target.value })}
                  className="w-full bg-page border border-th-border rounded-lg px-3 py-2 text-sm text-th-text focus:outline-none focus:border-th-border-focus"
                  autoFocus
                />
              </div>
              <div>
                <label className="block text-xs text-th-text-muted mb-1">Subject (optional)</label>
                <input
                  type="text"
                  value={receiptForm.subject}
                  onChange={(e) => setReceiptForm({ ...receiptForm, subject: e.target.value })}
                  className="w-full bg-page border border-th-border rounded-lg px-3 py-2 text-sm text-th-text focus:outline-none focus:border-th-border-focus"
                />
              </div>
              <div>
                <label className="block text-xs text-th-text-muted mb-1">Message (optional)</label>
                <textarea
                  rows={3}
                  value={receiptForm.message}
                  onChange={(e) => setReceiptForm({ ...receiptForm, message: e.target.value })}
                  className="w-full bg-page border border-th-border rounded-lg px-3 py-2 text-sm text-th-text focus:outline-none focus:border-th-border-focus resize-y"
                />
              </div>
            </div>
            <div className="flex justify-end gap-3 mt-4 pt-4 border-t border-th-border">
              <button
                onClick={() => setShowReceiptModal(null)}
                className="px-4 py-2 text-sm text-th-text-secondary hover:text-th-text transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={handleSendReceipt}
                disabled={receiptLoading || !receiptForm.to_email}
                className="px-4 py-2 text-sm font-medium bg-btn-primary-bg hover:bg-btn-primary-hover disabled:opacity-50 text-btn-primary-text rounded-lg transition-colors"
              >
                {receiptLoading ? 'Sending...' : 'Send Receipt'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Receive Payment Modal */}
      {showPaymentModal && (
        <ReceivePaymentModal
          invoice={invoice}
          onSave={handleRecordPayment}
          onClose={() => setShowPaymentModal(false)}
        />
      )}

      {/* Send Modal */}
      {showSendModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
          <div className="bg-surface rounded-xl border border-th-border p-6 w-full max-w-lg">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-lg font-semibold text-th-text">Send Invoice</h2>
              <button onClick={() => setShowSendModal(false)} className="text-th-text-muted hover:text-th-text">
                <X size={20} />
              </button>
            </div>

            <div className="space-y-4">
              <div>
                <label className="block text-xs text-th-text-muted mb-1">To Email</label>
                <input
                  type="email"
                  value={sendForm.to_email}
                  onChange={(e) => setSendForm({ ...sendForm, to_email: e.target.value })}
                  className="w-full bg-page border border-th-border rounded-lg px-3 py-2 text-sm text-th-text focus:outline-none focus:border-th-border-focus"
                  autoFocus
                />
              </div>
              <div>
                <label className="block text-xs text-th-text-muted mb-1">Subject</label>
                <input
                  type="text"
                  value={sendForm.subject}
                  onChange={(e) => setSendForm({ ...sendForm, subject: e.target.value })}
                  className="w-full bg-page border border-th-border rounded-lg px-3 py-2 text-sm text-th-text focus:outline-none focus:border-th-border-focus"
                />
              </div>
              <div>
                <label className="block text-xs text-th-text-muted mb-1">Message</label>
                <textarea
                  rows={4}
                  value={sendForm.message}
                  onChange={(e) => setSendForm({ ...sendForm, message: e.target.value })}
                  className="w-full bg-page border border-th-border rounded-lg px-3 py-2 text-sm text-th-text focus:outline-none focus:border-th-border-focus resize-y"
                />
              </div>
            </div>

            <div className="flex justify-end gap-3 mt-4 pt-4 border-t border-th-border">
              <button
                onClick={() => setShowSendModal(false)}
                className="px-4 py-2 text-sm text-th-text-secondary hover:text-th-text transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={handleSendInvoice}
                disabled={sendLoading || !sendForm.to_email}
                className="px-4 py-2 text-sm font-medium bg-btn-primary-bg hover:bg-btn-primary-hover disabled:opacity-50 text-btn-primary-text rounded-lg transition-colors"
              >
                {sendLoading ? 'Sending...' : 'Send'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
