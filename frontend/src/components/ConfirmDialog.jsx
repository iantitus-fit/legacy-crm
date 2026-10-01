export default function ConfirmDialog({
  isOpen,
  onConfirm,
  onCancel,
  title = 'Are you sure?',
  message = '',
  confirmLabel = 'Confirm',
  variant = 'danger',
}) {
  if (!isOpen) return null

  const buttonClass =
    variant === 'danger'
      ? 'bg-red-500 hover:bg-red-600 text-th-text'
      : 'bg-btn-primary-bg hover:bg-btn-primary-hover text-btn-primary-text'

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div
        className="absolute inset-0 bg-black/50 backdrop-blur-sm"
        onClick={onCancel}
      />
      <div className="relative bg-surface rounded-xl p-6 w-full max-w-sm mx-4 shadow-2xl">
        <h3 className="text-lg font-semibold text-th-text">{title}</h3>
        {message && (
          <p className="text-th-text-secondary text-sm mt-2">{message}</p>
        )}
        <div className="flex justify-end gap-3 mt-6">
          <button
            onClick={onCancel}
            className="px-4 py-2 text-sm text-th-text-secondary hover:text-th-text transition-colors"
          >
            Cancel
          </button>
          <button
            onClick={onConfirm}
            className={`px-4 py-2 rounded-lg text-sm font-semibold transition-colors ${buttonClass}`}
          >
            {confirmLabel}
          </button>
        </div>
      </div>
    </div>
  )
}
