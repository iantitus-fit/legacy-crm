import { useEffect, useRef, useState } from 'react'
import { Search, X } from 'lucide-react'

export default function SearchInput({ value, onChange, placeholder = 'Search...' }) {
  const [local, setLocal] = useState(value || '')
  const timerRef = useRef(null)

  useEffect(() => {
    setLocal(value || '')
  }, [value])

  const handleChange = (e) => {
    const val = e.target.value
    setLocal(val)
    clearTimeout(timerRef.current)
    timerRef.current = setTimeout(() => {
      onChange(val)
    }, 300)
  }

  const handleClear = () => {
    setLocal('')
    onChange('')
  }

  return (
    <div className="relative">
      <Search
        size={16}
        className="absolute left-3 top-1/2 -translate-y-1/2 text-th-text-muted"
      />
      <input
        type="text"
        value={local}
        onChange={handleChange}
        placeholder={placeholder}
        className="w-full bg-surface-hover border border-th-border-secondary rounded-lg pl-9 pr-8 py-2 text-sm text-th-text placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-brand-purple/50 focus:border-th-border-focus"
      />
      {local && (
        <button
          onClick={handleClear}
          className="absolute right-2 top-1/2 -translate-y-1/2 text-th-text-muted hover:text-th-text"
        >
          <X size={14} />
        </button>
      )}
    </div>
  )
}
