import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { setup } from '../api/auth'
import { getMe } from '../api/auth'
import { useAuth } from '../context/AuthContext'

export default function SetupPage() {
  const [fullName, setFullName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const navigate = useNavigate()

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError('')

    if (password !== confirmPassword) {
      setError('Passwords do not match')
      return
    }

    if (password.length < 8) {
      setError('Password must be at least 8 characters')
      return
    }

    setLoading(true)
    try {
      const { access_token } = await setup(email, fullName, password)
      localStorage.setItem('access_token', access_token)
      window.location.href = '/dashboard'
    } catch (err) {
      const detail = err.response?.data?.detail
      if (detail === 'Setup already completed') {
        setError('An admin account already exists. Please log in instead.')
      } else if (detail) {
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
          <p className="text-th-text-secondary text-sm mt-1">Create your admin account</p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-th-text-secondary mb-1">
              Full Name
            </label>
            <input
              type="text"
              value={fullName}
              onChange={(e) => setFullName(e.target.value)}
              required
              className="w-full bg-input border border-th-border-secondary rounded-lg px-4 py-2.5 text-th-text placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-brand-purple/50 focus:border-th-border-focus"
              placeholder="Dale Smith"
            />
          </div>

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
              placeholder="dale@legacy-roofing.example"
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
              placeholder="At least 8 characters"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-th-text-secondary mb-1">
              Confirm Password
            </label>
            <input
              type="password"
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              required
              className="w-full bg-input border border-th-border-secondary rounded-lg px-4 py-2.5 text-th-text placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-brand-purple/50 focus:border-th-border-focus"
              placeholder="Re-enter your password"
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
            {loading ? 'Creating account...' : 'Create Account'}
          </button>
        </form>

        <p className="text-center text-th-text-muted text-sm mt-6">
          Already set up?{' '}
          <Link to="/login" className="text-brand-purple hover:text-brand-purple-text">
            Log in
          </Link>
        </p>
      </div>
    </div>
  )
}
