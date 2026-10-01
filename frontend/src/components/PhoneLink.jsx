import { phoneHref } from '../utils/links'

/**
 * Renders a phone number as a clickable `tel:` link. Falls back to a dash
 * when there's no phone. The display text defaults to the phone value but
 * callers can override via children.
 *
 * Props:
 * - phone: the raw phone string to link
 * - className: applied to the <a>
 * - placeholder: text to show when phone is empty (default "—")
 */
export default function PhoneLink({ phone, className = '', placeholder = '—', children }) {
  if (!phone) {
    return <span className={className}>{placeholder}</span>
  }
  const href = phoneHref(phone)
  if (!href) {
    return <span className={className}>{phone}</span>
  }
  return (
    <a
      href={href}
      className={`hover:text-amber-500 transition-colors ${className}`}
      onClick={(e) => e.stopPropagation()}
    >
      {children || phone}
    </a>
  )
}
