import { Link } from 'react-router-dom'
import { ArrowLeft } from 'lucide-react'

/**
 * Consistent back-navigation button for detail pages.
 *
 * Always navigates to the supplied `to` path — we do NOT use `navigate(-1)`
 * because detail pages are reached via deep links (email, bookmarks, direct
 * URL) often enough that history-based back is unreliable.
 */
export default function BackButton({ to, label = 'Back' }) {
  return (
    <Link
      to={to}
      className="inline-flex items-center gap-1.5 text-sm text-slate-400 hover:text-brand-purple transition-colors mb-3"
    >
      <ArrowLeft size={16} />
      {label}
    </Link>
  )
}
