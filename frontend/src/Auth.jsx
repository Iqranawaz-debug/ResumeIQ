import { useState } from 'react'
import BrandMark from './BrandMark'
import ThemeToggle from './ThemeToggle'
import { API_BASE_URL, apiRequest } from './api'

const SIGNUP_URL = `${API_BASE_URL}/api/signup`
const LOGIN_URL = `${API_BASE_URL}/api/login`

const BRAND_COPY = {
  login: {
    headline: 'Screen resumes in seconds, not hours.',
    copy: 'Sign in to pick up where you left off — your recent evaluations are waiting.',
  },
  signup: {
    headline: 'Give every candidate a fair, fast read.',
    copy: 'ResumeIQ turns a stack of resumes into clear, screener-friendly summaries.',
  },
}

function Auth({ onAuthSuccess, theme, onToggleTheme }) {
  const [mode, setMode] = useState('login') // login | signup
  const [fullName, setFullName] = useState('')
  const [company, setCompany] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [submitting, setSubmitting] = useState(false)

  async function handleSubmit(event) {
    event.preventDefault()
    setError('')
    setSubmitting(true)

    const url = mode === 'login' ? LOGIN_URL : SIGNUP_URL
    const body =
      mode === 'login'
        ? { email, password }
        : { email, password, full_name: fullName, company }

    try {
      const data = await apiRequest(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      })
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

  const brand = BRAND_COPY[mode]

  return (
    <div className="auth-page">
      <div className="auth-panel auth-panel-form">
        <div className="auth-form-wrap">
          <h2>{mode === 'login' ? 'Welcome back' : 'Create your account'}</h2>
          <p className="auth-subtitle">
            {mode === 'login' ? 'New here? ' : 'Already have an account? '}
            <button type="button" className="link-button" onClick={toggleMode}>
              {mode === 'login' ? 'Create an account' : 'Sign in'}
            </button>
          </p>

          <form className="auth-form" onSubmit={handleSubmit}>
            {mode === 'signup' && (
              <label>
                Full name
                <input
                  type="text"
                  value={fullName}
                  onChange={(e) => setFullName(e.target.value)}
                  required
                />
              </label>
            )}

            <label>
              Work email
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
              />
            </label>

            {mode === 'signup' && (
              <label>
                Company
                <input
                  type="text"
                  value={company}
                  onChange={(e) => setCompany(e.target.value)}
                />
              </label>
            )}

            <label>
              Password
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                minLength={6}
              />
              <span className="auth-input-hint">At least 6 characters</span>
            </label>

            {error && <p className="status error">{error}</p>}

            <button className="evaluate-button auth-submit" type="submit" disabled={submitting}>
              {submitting ? 'Please wait...' : mode === 'login' ? 'Sign In' : 'Create Account'}
            </button>
          </form>
        </div>
      </div>

      <div className="auth-panel auth-panel-brand">
        <div className="auth-brand-row">
          <div className="brand">
            <BrandMark />
            <span className="brand-name">ResumeIQ</span>
          </div>
          <ThemeToggle theme={theme} onToggle={onToggleTheme} />
        </div>

        <h1 className="auth-headline">{brand.headline}</h1>
        <p className="auth-copy">{brand.copy}</p>

        <div className="auth-preview-card">
          <div className="score-row">
            <div className="score-ring" style={{ '--score': 92 }}>
              <div className="score-ring-inner">
                <span className="score-number">92</span>
                <span className="score-max">/ 100</span>
              </div>
            </div>
            <div>
              <p className="recommendation-badge rec-highly">Highly Recommended</p>
              <p className="experience-level">Sarah Chen · Senior PM</p>
            </div>
          </div>
          <div className="breakdown">
            <div className="breakdown-row">
              <span className="breakdown-label">skills</span>
              <div className="breakdown-track">
                <div className="breakdown-fill" style={{ width: '90%' }} />
              </div>
              <span className="breakdown-value">90%</span>
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
    </div>
  )
}

export default Auth
