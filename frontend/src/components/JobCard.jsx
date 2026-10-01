import { useSortable } from '@dnd-kit/sortable'
import { CSS } from '@dnd-kit/utilities'
import { useNavigate } from 'react-router-dom'
import AddressLink from './AddressLink'

function WorkTypeBadge({ type }) {
  if (type === 'insurance') {
    return (
      <span className="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-medium bg-blue-500/20 text-blue-400">
        Ins
      </span>
    )
  }
  if (type === 'retail') {
    return (
      <span className="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-medium bg-emerald-500/20 text-emerald-400">
        Ret
      </span>
    )
  }
  return null
}

const formatCurrency = (value) => {
  if (!value) return null
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(value)
}

/**
 * Pure display component — no dnd-kit hooks.
 * Used directly by DragOverlay and wrapped by JobCard for columns.
 */
export function JobCardContent({ job, className, style, onClick, innerRef, ...rest }) {
  return (
    <div
      ref={innerRef}
      style={style}
      className={className}
      onClick={onClick}
      {...rest}
    >
      {/* Contact name */}
      <p className="text-sm font-medium text-th-text truncate">
        {job.contact_name || 'No contact'}
      </p>

      {/* Property address */}
      {job.property_address && (
        <p className="text-xs text-th-text-secondary truncate mt-0.5">
          <AddressLink address={job.property_address} className="text-th-text-secondary" />
        </p>
      )}

      {/* Bottom row: badges + value */}
      <div className="flex items-center justify-between mt-2">
        <div className="flex items-center gap-1.5">
          <WorkTypeBadge type={job.work_type} />
          {job.job_type && (
            <span className="text-[10px] text-th-text-muted capitalize">
              {job.job_type}
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
export default function JobCard({ job }) {
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

  return (
    <JobCardContent
      job={job}
      innerRef={setNodeRef}
      style={style}
      className="bg-surface-hover hover:bg-th-border-secondary rounded-lg p-3 cursor-grab active:cursor-grabbing transition-colors"
      onClick={() => navigate(`/jobs/${job.id}`)}
      {...attributes}
      {...listeners}
    />
  )
}
