import { useEffect, useState } from 'react'
import { X, Search, Loader2 } from 'lucide-react'
import { listMaterials } from '../api/materials'

/**
 * Searchable material picker. When the user selects a material, calls
 * `onSelect(material)` with the full material record. The parent is
 * responsible for closing the picker and opening the edit modal pre-filled.
 */
export default function MaterialPickerModal({ onClose, onSelect }) {
  const [query, setQuery] = useState('')
  const [results, setResults] = useState([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  // Debounced search
  useEffect(() => {
    const handle = setTimeout(async () => {
      if (!query || query.trim().length < 2) {
        setResults([])
        return
      }
      setLoading(true)
      setError(null)
      try {
        const data = await listMaterials({ search: query.trim(), perPage: 20 })
        setResults(data.items || [])
      } catch (err) {
        setError('Failed to search materials')
        setResults([])
      } finally {
        setLoading(false)
      }
    }, 250)
    return () => clearTimeout(handle)
  }, [query])

  const formatMoney = (value) => {
    const n = Number(value || 0)
    return `$${n.toFixed(2)}`
  }

  return (
    <div
      className="fixed inset-0 bg-black/60 flex items-start justify-center z-50 pt-20"
      onClick={onClose}
    >
      <div
        className="bg-surface border border-th-border rounded-lg w-full max-w-2xl max-h-[70vh] flex flex-col"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between p-4 border-b border-th-border">
          <h2 className="text-lg font-semibold text-th-text">Search Materials</h2>
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
              placeholder="Type at least 2 characters..."
              className="w-full pl-9 pr-3 py-2 bg-page border border-th-border rounded text-th-text placeholder-slate-500 focus:outline-none focus:border-th-border-focus"
            />
          </div>
        </div>

        <div className="flex-1 overflow-y-auto">
          {loading && (
            <div className="flex items-center justify-center py-8 text-slate-400">
              <Loader2 className="animate-spin mr-2" size={16} />
              Searching...
            </div>
          )}
          {error && (
            <div className="p-4 text-red-400 text-sm">{error}</div>
          )}
          {!loading && !error && query.trim().length >= 2 && results.length === 0 && (
            <div className="p-4 text-slate-400 text-sm">No materials found.</div>
          )}
          {!loading && results.length > 0 && (
            <ul className="divide-y divide-slate-700">
              {results.map((material) => (
                <li key={material.id}>
                  <button
                    type="button"
                    onClick={() => onSelect(material)}
                    className="w-full text-left px-4 py-3 hover:bg-page transition-colors"
                  >
                    <div className="flex justify-between items-start gap-3">
                      <div className="flex-1 min-w-0">
                        <div className="text-sm text-th-text truncate">
                          {material.description || '(no description)'}
                        </div>
                        <div className="text-xs text-slate-400 mt-0.5">
                          {material.item_number && (
                            <span className="mr-2">#{material.item_number}</span>
                          )}
                          {material.uom && <span>per {material.uom}</span>}
                        </div>
                      </div>
                      <div className="font-mono text-sm text-brand-purple whitespace-nowrap">
                        {formatMoney(material.unit_price)}
                      </div>
                    </div>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </div>
  )
}
