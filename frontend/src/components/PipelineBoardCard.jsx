import { useSortable } from '@dnd-kit/sortable'
import { CSS } from '@dnd-kit/utilities'
import { useNavigate } from 'react-router-dom'
import AddressLink from './AddressLink'

const formatCurrency = (value) => {
  if (!value) return null
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(value)
}

function getInitials(name) {
  if (!name) return '?'
  return name
    .split(' ')
    .map((w) => w[0])
    .join('')
    .toUpperCase()
    .slice(0, 2)
}

function timeAgo(dateStr) {
  if (!dateStr) return null
  const now = new Date()
  const then = new Date(dateStr)
  const diffMs = now - then
  const diffMins = Math.floor(diffMs / 60000)
  if (diffMins < 1) return 'just now'
  if (diffMins < 60) return `${diffMins}m ago`
  const diffHours = Math.floor(diffMins / 60)
  if (diffHours < 24) return `${diffHours}h ago`
  const diffDays = Math.floor(diffHours / 24)
  if (diffDays < 7) return `${diffDays}d ago`
  return then.toLocaleDateString()
}

/**
 * Pure display component — no dnd-kit hooks.
 * Used directly by DragOverlay and wrapped by PipelineBoardCard for columns.
 */
export function PipelineBoardCardContent({ job, className, style, onClick, innerRef, ...rest }) {
  return (
    <div
      ref={innerRef}
      style={style}
      className={className}
      onClick={onClick}
      {...rest}
    >
      {/* Top row: contact name + assigned initials */}
      <div className="flex items-start justify-between gap-2">
        <p className="text-sm font-medium text-th-text truncate flex-1">
          {job.contact_name || job.display_name || 'No contact'}
        </p>
        {job.assigned_to_name && (
          <span
            className="shrink-0 w-6 h-6 rounded-full bg-badge-warning-bg text-brand-purple text-[10px] font-bold flex items-center justify-center"
            title={job.assigned_to_name}
          >
            {getInitials(job.assigned_to_name)}
          </span>
        )}
      </div>

      {/* Property address */}
      {job.property_address && (
        <p className="text-xs text-th-text-secondary truncate mt-0.5">
          <AddressLink address={job.property_address} className="text-th-text-secondary" />
        </p>
      )}

      {/* Middle row: lead source + labels */}
      <div className="flex items-center gap-1.5 mt-2 flex-wrap">
        {job.lead_source && (
          <span className="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-medium bg-blue-500/20 text-blue-400">
            {job.lead_source}
          </span>
        )}
        {job.labels &&
          job.labels.map((label) => (
            <span
              key={label}
              className="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-medium bg-purple-500/20 text-purple-400"
            >
              {label}
            </span>
          ))}
      </div>

      {/* Bottom row: value + last activity */}
      <div className="flex items-center justify-between mt-2">
        <div className="flex items-center gap-1.5">
          {job.work_type === 'insurance' && (
            <span className="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-medium bg-blue-500/20 text-blue-400">
              Ins
            </span>
          )}
          {job.work_type === 'retail' && (
            <span className="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-medium bg-emerald-500/20 text-emerald-400">
              Ret
            </span>
          )}
          {job.last_activity_at && (
            <span className="text-[10px] text-th-text-muted">
              {timeAgo(job.last_activity_at)}
            </span>
          )}
        </div>
        {job.contract_value && (
          <span className="text-xs font-mono text-brand-purple">
            {formatCurrency(job.contract_value)}
          </span>
        )}
      </div>
    </div>
  )
}

/**
 * Sortable wrapper — used inside SortableContext columns only.
 * Never render this inside DragOverlay.
 */
export default function PipelineBoardCard({ job }) {
  const navigate = useNavigate()
  const {
    attributes,
    listeners,
    setNodeRef,
    transform,
    transition,
    isDragging,
  } = useSortable({ id: `job-${job.id}`, data: { job } })

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
    opacity: isDragging ? 0 : undefined,
  }

  // Sprint 15c — route based on entity type set by the board fetcher.
  // contact → client profile, estimate → estimate detail, job → job detail.
  const handleClick = () => {
    if (job._entity_type === 'contact') {
      navigate(`/contacts/${job.id}`)
    } else if (job._entity_type === 'estimate') {
      navigate(`/estimates/${job.id}`)
    } else {
      navigate(`/jobs/${job.id}`)
    }
  }

  return (
    <PipelineBoardCardContent
      job={job}
      innerRef={setNodeRef}
      style={style}
      className="bg-surface-hover hover:bg-th-border-secondary rounded-lg p-3 cursor-grab active:cursor-grabbing transition-colors"
      onClick={handleClick}
      {...attributes}
      {...listeners}
    />
  )
}
