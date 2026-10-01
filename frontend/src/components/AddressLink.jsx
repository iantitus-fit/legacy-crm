import { mapHref } from '../utils/links'

/**
 * Renders a mailing/street address as a clickable Apple Maps link. On
 * iOS the link opens Apple Maps directly; on other platforms the URL
 * opens in a browser-based map. Falls back to a dash when empty.
 *
 * Props:
 * - address: the address string to render
 * - className: applied to the <a>
 * - placeholder: text to show when empty (default "—")
 */
export default function AddressLink({ address, className = '', placeholder = '—', children }) {
  if (!address) {
    return <span className={className}>{placeholder}</span>
  }
  return (
    <a
      href={mapHref(address)}
      target="_blank"
      rel="noreferrer"
      className={`hover:text-amber-500 transition-colors ${className}`}
      onClick={(e) => e.stopPropagation()}
    >
      {children || address}
    </a>
  )
}
