export default function EmptyState({ icon: Icon, title, description, action }) {
  return (
    <div className="flex flex-col items-center justify-center py-16 text-center">
      {Icon && (
        <div className="bg-surface-hover rounded-full p-4 mb-4">
          <Icon size={32} className="text-th-text-muted" />
        </div>
      )}
      <h3 className="text-lg font-medium text-th-text">{title}</h3>
      {description && (
        <p className="text-th-text-muted text-sm mt-1 max-w-sm">{description}</p>
      )}
      {action && <div className="mt-4">{action}</div>}
    </div>
  )
}
