import { useEffect, useRef, useState } from 'react'
import {
  ChevronDown,
  Copy,
  Eye,
  HardHat,
  Mail,
  ShieldAlert,
} from 'lucide-react'
import {
  fetchWorkOrderBlobUrl,
  getWorkOrderLink,
} from '../api/workOrders'
import { useToast } from '../context/ToastContext'

/**
 * Dropdown button for work orders. Standard + Secret variants.
 *
 * Props:
 * - estimateId: number
 * - onSend: (secret: boolean) => void  — parent opens the WorkOrderSendModal
 */
export default function WorkOrderDropdown({ estimateId, onSend }) {
  const { addToast } = useToast()
  const [open, setOpen] = useState(false)
  const [busy, setBusy] = useState(false)
  const menuRef = useRef(null)

  useEffect(() => {
    if (!open) return
    const handle = (e) => {
      if (menuRef.current && !menuRef.current.contains(e.target)) {
        setOpen(false)
      }
    }
    document.addEventListener('mousedown', handle)
    return () => document.removeEventListener('mousedown', handle)
  }, [open])

  const close = () => setOpen(false)

  const handleView = async (secret) => {
    close()
    setBusy(true)
    try {
      const blobUrl = await fetchWorkOrderBlobUrl(estimateId, secret)
      window.open(blobUrl, '_blank', 'noopener,noreferrer')
    } catch (err) {
      addToast(
        err.response?.data?.detail || 'Failed to load work order',
        'error'
      )
    } finally {
      setBusy(false)
    }
  }

  const handleCopy = async (secret) => {
    close()
    setBusy(true)
    try {
      const { url } = await getWorkOrderLink(estimateId, secret)
      await navigator.clipboard.writeText(url)
      addToast(secret ? 'Secret work order link copied' : 'Work order link copied')
    } catch (err) {
      addToast(
        err.response?.data?.detail || 'Failed to copy link',
        'error'
      )
    } finally {
      setBusy(false)
    }
  }

  const handleSend = (secret) => {
    close()
    onSend?.(secret)
  }

  return (
    <div className="relative inline-flex" ref={menuRef}>
      <button
        type="button"
        onClick={() => setOpen((p) => !p)}
        disabled={busy}
        className="flex items-center gap-1.5 px-3 py-1.5 text-sm text-th-text-secondary hover:text-th-text hover:bg-surface rounded-lg transition-colors disabled:opacity-50"
        aria-haspopup="menu"
        aria-expanded={open}
      >
        <HardHat size={15} />
        Work Order
        <ChevronDown size={13} />
      </button>
      {open && (
        <div className="absolute top-full right-0 mt-1 w-60 bg-surface border border-th-border rounded shadow-lg z-30">
          <div className="px-3 py-1.5 text-[10px] font-semibold uppercase tracking-wider text-th-text-muted border-b border-th-border">
            Standard
          </div>
          <MenuItem icon={Mail} onClick={() => handleSend(false)}>
            Send Work Order
          </MenuItem>
          <MenuItem icon={Eye} onClick={() => handleView(false)}>
            View Work Order
          </MenuItem>
          <MenuItem icon={Copy} onClick={() => handleCopy(false)}>
            Copy Link
          </MenuItem>
          <div className="px-3 py-1.5 text-[10px] font-semibold uppercase tracking-wider text-th-text-muted border-y border-th-border">
            <ShieldAlert
              size={11}
              className="inline-block mr-1 -mt-0.5 text-amber-500"
            />
            Secret (no customer info)
          </div>
          <MenuItem icon={Mail} onClick={() => handleSend(true)}>
            Send Secret Work Order
          </MenuItem>
          <MenuItem icon={Eye} onClick={() => handleView(true)}>
            View Secret Work Order
          </MenuItem>
          <MenuItem icon={Copy} onClick={() => handleCopy(true)}>
            Copy Secret Link
          </MenuItem>
        </div>
      )}
    </div>
  )
}

function MenuItem({ icon: Icon, onClick, children }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="w-full flex items-center gap-2 px-3 py-2 text-sm text-th-text hover:bg-page text-left transition-colors"
    >
      <Icon size={14} className="text-th-text-muted shrink-0" />
      {children}
    </button>
  )
}
