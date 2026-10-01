import { Link } from 'react-router-dom'

export default function NotFoundPage() {
  return (
    <div className="flex flex-col items-center justify-center min-h-screen bg-page px-4">
      <h1 className="text-6xl font-bold text-gray-700">404</h1>
      <p className="text-gray-400 mt-4 text-lg">Page not found</p>
      <Link
        to="/dashboard"
        className="mt-6 text-amber-500 hover:text-amber-400 text-sm"
      >
        Back to Dashboard
      </Link>
    </div>
  )
}
