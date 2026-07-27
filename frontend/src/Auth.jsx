import { useState } from 'react'
import BrandMark from './BrandMark'
import ThemeToggle from './ThemeToggle'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8001'
const SIGNUP_URL = `${API_BASE_URL}/api/signup`
const LOGIN_URL = `${API_BASE_URL}/api/login`

function Auth({ onAuthSuccess, theme, onToggleTheme }) {
  const [mode, setMode] = useState('login') // login | signup
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [submitting, setSubmitting] = useState(false)

  async function handleSubmit(event) {
    event.preventDefault()
    setError('')
    setSubmitting(true)

    const url = mode === 'login' ? LOGIN_URL : SIGNUP_URL

    try {
      const response = await fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password }),
      })
      const data = await response.json()

      if (!response.ok) {
        throw new Error(data.detail || 'Something went wrong.')
      }

      onAuthSuccess(data.token, data.username)
    } catch (err) {
      setError(err.message || 'Could not reach the server.')
    } finally {
      setSubmitting(false)
    }
  }

  function toggleMode() {
    setMode(mode === 'login' ? 'signup' : 'login')
    setError('')
  }

  return (
    <div className="auth-page">
      <div className="auth-panel auth-panel-brand">
        <div className="auth-brand-row">
          <div className="brand">
            <BrandMark />
            <span className="brand-name">ResumeIQ</span>
          </div>
          <ThemeToggle theme={theme} onToggle={onToggleTheme} />
        </div>

        <h1 className="auth-headline">
          Screen every candidate resume in seconds, not hours.
        </h1>
        <p className="auth-copy">
          AI-powered scoring across contact info, skills, education, and
          experience — with a hiring recommendation in seconds.
        </p>

        <div className="auth-preview-card">
          <div className="score-row">
            <div className="score-ring" style={{ '--score': 82 }}>
              <div className="score-ring-inner">
                <span className="score-number">82</span>
                <span className="score-max">/ 100</span>
              </div>
            </div>
            <div>
              <p className="recommendation-badge rec-highly">Highly Recommended</p>
              <p className="experience-level">Senior</p>
            </div>
          </div>
          <div className="breakdown">
            <div className="breakdown-row">
              <span className="breakdown-label">skills</span>
              <div className="breakdown-track">
                <div className="breakdown-fill" style={{ width: '80%' }} />
              </div>
              <span className="breakdown-value">80%</span>
            </div>
            <div className="breakdown-row">
              <span className="breakdown-label">experience</span>
              <div className="breakdown-track">
                <div className="breakdown-fill" style={{ width: '100%' }} />
              </div>
              <span className="breakdown-value">100%</span>
            </div>
          </div>
        </div>
      </div>

      <div className="auth-panel auth-panel-form">
        <div className="auth-form-wrap">
          <p className="eyebrow">{mode === 'login' ? '/ SIGN IN' : '/ CREATE ACCOUNT'}</p>
          <h2>{mode === 'login' ? 'Welcome back' : 'Get started'}</h2>
          <p className="auth-subtitle">
            {mode === 'login'
              ? 'Sign in to continue scoring resumes.'
              : 'Create an account to start scoring resumes.'}
          </p>

          <form className="auth-form" onSubmit={handleSubmit}>
            <label>
              Email
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
              />
            </label>

            <label>
              Password
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                minLength={6}
              />
            </label>

            {error && <p className="status error">{error}</p>}

            <button className="evaluate-button auth-submit" type="submit" disabled={submitting}>
              {submitting ? 'Please wait...' : mode === 'login' ? 'Sign In' : 'Sign Up'}
            </button>
          </form>

          <p className="auth-toggle">
            {mode === 'login' ? "Don't have an account? " : 'Already have an account? '}
            <button type="button" className="link-button" onClick={toggleMode}>
              {mode === 'login' ? 'Sign Up' : 'Sign In'}
            </button>
          </p>
        </div>
      </div>
    </div>
  )
}

export default Auth
