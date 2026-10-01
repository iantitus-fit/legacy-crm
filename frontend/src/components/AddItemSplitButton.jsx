import { useEffect, useRef, useState } from 'react'
import { Plus, ChevronDown, FileText, Package } from 'lucide-react'

/**
 * Split button for adding a line item. Main click = blank item. Chevron click
 * = dropdown with "Blank Item" and "From Materials" options.
 *
 * Props:
 * - onAddBlank: () => void
 * - onAddFromMaterials: () => void
 * - label: optional main button text (default "Add Item")
 */
export default function AddItemSplitButton({
  onAddBlank,
  onAddFromMaterials,
  label = 'Add Item',
}) {
  const [open, setOpen] = useState(false)
  const menuRef = useRef(null)

  useEffect(() => {
    if (!open) return
    const handleClick = (e) => {
      if (menuRef.current && !menuRef.current.contains(e.target)) {
        setOpen(false)
      }
    }
    document.addEventListener('mousedown', handleClick)
    return () => document.removeEventListener('mousedown', handleClick)
  }, [open])

  const handleBlank = () => {
    setOpen(false)
    onAddBlank()
  }

  const handleFromMaterials = () => {
    setOpen(false)
    onAddFromMaterials()
  }

  return (
    <div className="relative inline-flex" ref={menuRef}>
      <button
        type="button"
        onClick={handleBlank}
        className="inline-flex items-center gap-1 px-3 py-1.5 text-xs bg-btn-primary-bg hover:bg-btn-primary-hover text-btn-primary-text font-semibold rounded-l border-r border-amber-700"
      >
        <Plus size={14} />
        {label}
      </button>
      <button
        type="button"
        onClick={() => setOpen((prev) => !prev)}
        className="inline-flex items-center px-2 py-1.5 bg-btn-primary-bg hover:bg-btn-primary-hover text-btn-primary-text rounded-r"
        aria-label="More add options"
        aria-expanded={open}
        aria-haspopup="menu"
      >
        <ChevronDown size={14} />
      </button>
      {open && (
        <div className="absolute top-full right-0 mt-1 w-52 bg-surface border border-th-border rounded shadow-lg z-30">
          <button
            type="button"
            onClick={handleBlank}
            className="w-full flex items-center gap-2 px-3 py-2 text-sm text-th-text hover:bg-page text-left"
          >
            <FileText size={14} className="text-slate-400" />
            Blank Item
          </button>
          <button
            type="button"
            onClick={handleFromMaterials}
            className="w-full flex items-center gap-2 px-3 py-2 text-sm text-th-text hover:bg-page text-left border-t border-th-border"
          >
            <Package size={14} className="text-slate-400" />
            From Materials
          </button>
        </div>
      )}
    </div>
  )
}
