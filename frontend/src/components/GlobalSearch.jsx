import { useState, useEffect, useRef, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { Search, Loader2 } from 'lucide-react'
import { searchContacts } from '../api/contacts'

function getInitials(name) {
  return name
    .split(' ')
    .slice(0, 2)
    .map((w) => w[0])
    .join('')
    .toUpperCase()
}

export default function GlobalSearch() {
  const [query, setQuery] = useState('')
  const [results, setResults] = useState([])
  const [loading, setLoading] = useState(false)
  const [open, setOpen] = useState(false)
  const [highlightIndex, setHighlightIndex] = useState(-1)
  const [mobileExpanded, setMobileExpanded] = useState(false)
  const containerRef = useRef(null)
  const inputRef = useRef(null)
  const navigate = useNavigate()
  const debounceRef = useRef(null)

  const doSearch = useCallback(async (q) => {
    if (q.length < 2) {
      setResults([])
      setOpen(false)
      return
    }
    setLoading(true)
    try {
      const data = await searchContacts(q)
      setResults(data)
      setOpen(true)
      setHighlightIndex(-1)
    } catch {
      setResults([])
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    clearTimeout(debounceRef.current)
    debounceRef.current = setTimeout(() => doSearch(query), 300)
    return () => clearTimeout(debounceRef.current)
  }, [query, doSearch])

  useEffect(() => {
    function handleClickOutside(e) {
      if (containerRef.current && !containerRef.current.contains(e.target)) {
        setOpen(false)
        setMobileExpanded(false)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  function selectResult(contact) {
    navigate(`/contacts/${contact.id}`)
    setQuery('')
    setResults([])
    setOpen(false)
    setMobileExpanded(false)
  }

  function handleKeyDown(e) {
    if (!open || results.length === 0) {
      if (e.key === 'Escape') {
        setOpen(false)
        setMobileExpanded(false)
        inputRef.current?.blur()
      }
      return
    }
    if (e.key === 'ArrowDown') {
      e.preventDefault()
      setHighlightIndex((i) => (i < results.length - 1 ? i + 1 : 0))
    } else if (e.key === 'ArrowUp') {
      e.preventDefault()
      setHighlightIndex((i) => (i > 0 ? i - 1 : results.length - 1))
    } else if (e.key === 'Enter' && highlightIndex >= 0) {
      e.preventDefault()
      selectResult(results[highlightIndex])
    } else if (e.key === 'Escape') {
      setOpen(false)
      inputRef.current?.blur()
    }
  }

  const cityState = (c) => {
    if (c.city && c.state) return `${c.city}, ${c.state}`
    return c.city || c.state || ''
  }

  return (
    <div ref={containerRef} className="relative w-full">
      {/* Desktop search bar */}
      <div className="hidden md:block relative">
        <Search
          size={16}
          className="absolute left-3 top-1/2 -translate-y-1/2 text-th-text-muted pointer-events-none"
        />
        {loading && (
          <Loader2
            size={16}
            className="absolute right-3 top-1/2 -translate-y-1/2 text-th-text-muted animate-spin"
          />
        )}
        <input
          ref={inputRef}
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onFocus={() => query.length >= 2 && results.length > 0 && setOpen(true)}
          onKeyDown={handleKeyDown}
          placeholder="Search clients..."
          className="w-full pl-9 pr-9 py-2 text-sm rounded-lg bg-surface border border-th-border text-th-text placeholder-th-text-muted focus:outline-none focus:ring-2 focus:ring-brand-purple/50 focus:border-brand-purple transition-colors"
        />
      </div>

      {/* Mobile: icon toggle */}
      <div className="md:hidden">
        {!mobileExpanded ? (
          <button
            onClick={() => {
              setMobileExpanded(true)
              setTimeout(() => inputRef.current?.focus(), 50)
            }}
            className="p-2 text-th-text-secondary hover:text-th-text bg-surface rounded-lg border border-th-border transition-colors"
          >
            <Search size={18} />
          </button>
        ) : (
          <div className="relative">
            <Search
              size={16}
              className="absolute left-3 top-1/2 -translate-y-1/2 text-th-text-muted pointer-events-none"
            />
            {loading && (
              <Loader2
                size={16}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-th-text-muted animate-spin"
              />
            )}
            <input
              ref={inputRef}
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onFocus={() => query.length >= 2 && results.length > 0 && setOpen(true)}
              onKeyDown={handleKeyDown}
              placeholder="Search clients..."
              className="w-full pl-9 pr-9 py-2 text-sm rounded-lg bg-surface border border-th-border text-th-text placeholder-th-text-muted focus:outline-none focus:ring-2 focus:ring-brand-purple/50 focus:border-brand-purple transition-colors"
            />
          </div>
        )}
      </div>

      {/* Dropdown */}
      {open && (
        <div className="absolute z-50 mt-1 w-full bg-surface border border-th-border rounded-lg shadow-lg overflow-hidden max-h-[360px] overflow-y-auto">
          {results.length === 0 && !loading ? (
            <div className="px-4 py-3 text-sm text-th-text-muted">No clients found</div>
          ) : (
            results.map((contact, i) => (
              <button
                key={contact.id}
                onClick={() => selectResult(contact)}
                onMouseEnter={() => setHighlightIndex(i)}
                className={`w-full text-left px-3 py-2.5 flex items-center gap-3 transition-colors ${
                  i === highlightIndex
                    ? 'bg-surface-hover'
                    : 'hover:bg-surface-hover'
                }`}
              >
                <div className="flex-shrink-0 w-9 h-9 rounded-full bg-brand-purple/20 text-brand-purple flex items-center justify-center text-xs font-semibold">
                  {getInitials(contact.name)}
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center justify-between">
                    <span className="text-sm font-medium text-th-text truncate">
                      {contact.name}
                    </span>
                    {contact.phone && (
                      <span className="text-xs text-th-text-muted font-mono ml-2 flex-shrink-0">
                        {contact.phone}
                      </span>
                    )}
                  </div>
                  {(contact.company || cityState(contact)) && (
                    <div className="text-xs text-th-text-secondary truncate">
                      {[contact.company, cityState(contact)].filter(Boolean).join(' · ')}
                    </div>
                  )}
                </div>
              </button>
            ))
          )}
        </div>
      )}
    </div>
  )
}
