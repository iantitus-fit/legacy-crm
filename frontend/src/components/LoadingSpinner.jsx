export default function LoadingSpinner({ size = 'md', centered = false }) {
  const sizes = {
    sm: 'h-4 w-4',
    md: 'h-8 w-8',
    lg: 'h-12 w-12',
  }

  const spinner = (
    <div className={`animate-spin rounded-full border-t-2 border-b-2 border-brand-purple ${sizes[size]}`} />
  )

  if (centered) {
    return <div className="flex justify-center py-16">{spinner}</div>
  }

  return spinner
}
