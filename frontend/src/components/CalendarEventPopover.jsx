import { useEffect, useRef } from 'react'
import { Link } from 'react-router-dom'
import { X, MapPin, Clock, User, Briefcase } from 'lucide-react'

const formatCurrency = (value) => {
  if (!value && value !== 0) return null
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(value)
}

const formatTime = (timeStr) => {
  if (!timeStr) return null
  const date = new Date(timeStr)
  return date.toLocaleTimeString('en-US', {
    hour: 'numeric',
    minute: '2-digit',
    hour12: true,
  })
}

const formatDuration = (minutes) => {
  if (!minutes) return null
  if (minutes < 60) return `${minutes}min`
  const hrs = Math.floor(minutes / 60)
  const mins = minutes % 60
  return mins > 0 ? `${hrs}h ${mins}m` : `${hrs}h`
}

export default function CalendarEventPopover({ event, position, onClose, variant = 'job' }) {
  const popoverRef = useRef(null)

  useEffect(() => {
    const handleClickOutside = (e) => {
      if (popoverRef.current && !popoverRef.current.contains(e.target)) {
        onClose()
      }
    }

    const handleEscape = (e) => {
      if (e.key === 'Escape') {
        onClose()
      }
    }

    document.addEventListener('mousedown', handleClickOutside)
    document.addEventListener('keydown', handleEscape)
    return () => {
      document.removeEventListener('mousedown', handleClickOutside)
      document.removeEventListener('keydown', handleEscape)
    }
  }, [onClose])

  return (
    <div
      ref={popoverRef}
      className="absolute bg-surface-hover border border-th-border-secondary rounded-xl shadow-xl p-4 z-50 w-72"
      style={{ top: position.top, left: position.left }}
    >
      {/* Close button */}
      <button
        onClick={onClose}
        className="absolute top-3 right-3 text-th-text-muted hover:text-th-text transition-colors"
      >
        <X size={16} />
      </button>

      {variant === 'job' ? (
        <JobContent event={event} />
      ) : (
        <AppointmentContent event={event} />
      )}
    </div>
  )
}

function JobContent({ event }) {
  return (
    <div className="space-y-3">
      {/* Title */}
      <div className="pr-6">
        <h3 className="text-sm font-semibold text-th-text leading-tight">
          {event.display_name || event.property_address || 'Untitled Job'}
        </h3>
      </div>

      {/* Details */}
      <div className="space-y-2">
        {event.contact_name && (
          <div className="flex items-center gap-2">
            <User size={14} className="text-th-text-muted shrink-0" />
            <span className="text-sm text-th-text">{event.contact_name}</span>
          </div>
        )}

        {event.crew_name && (
          <div className="flex items-center gap-2">
            <span
              className="w-2.5 h-2.5 rounded-full shrink-0"
              style={{ backgroundColor: event.crew_color || '#6B7280' }}
            />
            <span className="text-sm text-th-text">{event.crew_name}</span>
          </div>
        )}

        {event.stage_name && (
          <div className="flex items-center gap-2">
            <Briefcase size={14} className="text-th-text-muted shrink-0" />
            <span className="text-sm text-th-text">{event.stage_name}</span>
          </div>
        )}

        {event.contract_value != null && (
          <div className="flex items-center gap-2">
            <span className="text-xs font-medium text-th-text-muted shrink-0">$</span>
            <span className="text-sm font-mono text-brand-purple">
              {formatCurrency(event.contract_value)}
            </span>
          </div>
        )}
      </div>

      {/* Action link — Sprint 15d: calendar "jobs" are approved estimates */}
      <div className="pt-1 border-t border-th-border-secondary">
        <Link
          to={`/estimates/${event.id}`}
          className="text-sm text-brand-purple hover:text-brand-purple-text font-medium transition-colors"
        >
          View Job &rarr;
        </Link>
      </div>
    </div>
  )
}

function AppointmentContent({ event }) {
  return (
    <div className="space-y-3">
      {/* Title */}
      <div className="pr-6">
        <h3 className="text-sm font-semibold text-th-text leading-tight">
          {event.title || 'Untitled Appointment'}
        </h3>
      </div>

      {/* Details */}
      <div className="space-y-2">
        {event.contact_name && (
          <div className="flex items-center gap-2">
            <User size={14} className="text-th-text-muted shrink-0" />
            <span className="text-sm text-th-text">{event.contact_name}</span>
          </div>
        )}

        {(event.appointment_time || event.duration_minutes) && (
          <div className="flex items-center gap-2">
            <Clock size={14} className="text-th-text-muted shrink-0" />
            <span className="text-sm text-th-text">
              {formatTime(event.appointment_time)}
              {event.duration_minutes && (
                <span className="text-th-text-muted"> ({formatDuration(event.duration_minutes)})</span>
              )}
            </span>
          </div>
        )}

        {event.appointment_type && (
          <div className="flex items-center gap-2">
            <span className="inline-flex items-center px-2 py-0.5 rounded text-[11px] font-medium bg-btn-primary-bg/15 text-brand-purple-text capitalize">
              {event.appointment_type.replace('_', ' ')}
            </span>
          </div>
        )}

        {event.location && (
          <div className="flex items-center gap-2">
            <MapPin size={14} className="text-th-text-muted shrink-0" />
            <span className="text-sm text-th-text truncate">{event.location}</span>
          </div>
        )}
      </div>

      {/* Action link */}
      <div className="pt-1 border-t border-th-border-secondary">
        <Link
          to="/calendars/appointments"
          className="text-sm text-brand-purple hover:text-brand-purple-text font-medium transition-colors"
        >
          View Appointments &rarr;
        </Link>
      </div>
    </div>
  )
}
