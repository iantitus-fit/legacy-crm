import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'

export default function LoginPage() {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const { login } = useAuth()
  const navigate = useNavigate()

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      await login(email, password)
      navigate('/dashboard')
    } catch (err) {
      const detail = err.response?.data?.detail
      if (detail) {
        setError(detail)
      } else {
        setError('Unable to connect. Please check your connection.')
      }
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="flex items-center justify-center min-h-screen bg-page px-4">
      <div className="bg-surface rounded-xl shadow-th-lg p-8 w-full max-w-md border border-th-border">
        <div className="text-center mb-8">
          <h1 className="text-2xl font-bold text-brand-purple">Legacy CRM</h1>
          <p className="text-th-text-muted text-sm mt-1">Roofing &amp; Exteriors</p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-th-text-secondary mb-1">
              Email
            </label>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              className="w-full bg-input border border-th-border-secondary rounded-lg px-4 py-2.5 text-th-text placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-brand-purple/50 focus:border-th-border-focus"
              placeholder="you@example.com"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-th-text-secondary mb-1">
              Password
            </label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              className="w-full bg-input border border-th-border-secondary rounded-lg px-4 py-2.5 text-th-text placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-brand-purple/50 focus:border-th-border-focus"
              placeholder="Enter your password"
            />
          </div>

          {error && (
            <p className="text-red-400 text-sm">{error}</p>
          )}

          <button
            type="submit"
            disabled={loading}
            className="w-full bg-btn-primary-bg hover:bg-btn-primary-hover text-btn-primary-text font-semibold py-2.5 rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {loading ? 'Logging in...' : 'Log In'}
          </button>
        </form>

        <p className="text-center text-th-text-muted text-sm mt-6">
          First time?{' '}
          <Link to="/setup" className="text-brand-purple hover:text-brand-purple-text">
            Set up your account
          </Link>
        </p>
      </div>
    </div>
  )
}
