import { useEffect, useRef, useState } from 'react'
import Auth from './Auth'
import BrandMark from './BrandMark'
import './App.css'

const UPLOAD_URL = 'http://localhost:8001/api/upload'
const ANALYZE_URL = 'http://localhost:8001/api/analyze'
const HISTORY_URL = 'http://localhost:8001/api/history'
const LOGOUT_URL = 'http://localhost:8001/api/logout'
const ALLOWED_EXTENSIONS = ['pdf', 'docx']
const MAX_FILE_SIZE_MB = 10

const RECOMMENDATION_CLASS = {
  'Highly Recommended': 'rec-highly',
  Recommended: 'rec-recommended',
  Consider: 'rec-consider',
  'Not Recommended': 'rec-not',
}

function getExtension(filename) {
  return filename.includes('.') ? filename.split('.').pop().toLowerCase() : ''
}

function validateFile(file) {
  const extension = getExtension(file.name)
  if (!ALLOWED_EXTENSIONS.includes(extension)) {
    return 'Invalid file type. Please upload a PDF or DOCX file.'
  }
  if (file.size === 0) {
    return 'The uploaded file is empty.'
  }
  if (file.size > MAX_FILE_SIZE_MB * 1024 * 1024) {
    return `File size exceeds the ${MAX_FILE_SIZE_MB}MB limit.`
  }
  return null
}

function App() {
  const [token, setToken] = useState(() => localStorage.getItem('resumeiq_token'))
  const [username, setUsername] = useState(() => localStorage.getItem('resumeiq_username'))

  const [isDragging, setIsDragging] = useState(false)
  const [uploadStatus, setUploadStatus] = useState('idle') // idle | uploading | success | error
  const [uploadMessage, setUploadMessage] = useState('')
  const [fileName, setFileName] = useState('')
  const [candidate, setCandidate] = useState(null)

  const [jdInputMode, setJdInputMode] = useState('text') // text | file
  const [jobDescription, setJobDescription] = useState('')
  const [jdFile, setJdFile] = useState(null)
  const [analysisStatus, setAnalysisStatus] = useState('idle') // idle | analyzing | success | error
  const [analysisMessage, setAnalysisMessage] = useState('')
  const [analysis, setAnalysis] = useState(null)
  const [history, setHistory] = useState([])

  const inputRef = useRef(null)
  const jdFileRef = useRef(null)

  useEffect(() => {
    if (!token) return
    fetch(HISTORY_URL, { headers: { Authorization: `Bearer ${token}` } })
      .then((res) => {
        if (res.status === 401) {
          localStorage.removeItem('resumeiq_token')
          localStorage.removeItem('resumeiq_username')
          setToken(null)
          setUsername(null)
          return { history: [] }
        }
        return res.ok ? res.json() : { history: [] }
      })
      .then((data) => setHistory(data.history || []))
      .catch(() => {})
  }, [token])

  function handleAuthSuccess(newToken, newUsername) {
    localStorage.setItem('resumeiq_token', newToken)
    localStorage.setItem('resumeiq_username', newUsername)
    setToken(newToken)
    setUsername(newUsername)
  }

  async function handleLogout() {
    try {
      await fetch(LOGOUT_URL, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` },
      })
    } catch {
      // ignore network errors on logout
    }
    localStorage.removeItem('resumeiq_token')
    localStorage.removeItem('resumeiq_username')
    setToken(null)
    setUsername(null)
    setUploadStatus('idle')
    setCandidate(null)
    setAnalysis(null)
    setAnalysisStatus('idle')
    setHistory([])
    setJobDescription('')
    setJdFile(null)
  }

  if (!token) {
    return <Auth onAuthSuccess={handleAuthSuccess} />
  }

  async function uploadFile(file) {
    const clientError = validateFile(file)
    if (clientError) {
      setUploadStatus('error')
      setUploadMessage(clientError)
      setFileName('')
      setCandidate(null)
      setAnalysis(null)
      setAnalysisStatus('idle')
      return
    }

    setUploadStatus('uploading')
    setUploadMessage('')
    setAnalysis(null)
    setAnalysisStatus('idle')

    const formData = new FormData()
    formData.append('file', file)

    try {
      const response = await fetch(UPLOAD_URL, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` },
        body: formData,
      })
      const data = await response.json()

      if (!response.ok) {
        throw new Error(data.detail || 'Upload failed.')
      }

      setUploadStatus('success')
      setUploadMessage(data.message)
      setFileName(data.filename)
      setCandidate(data.candidate || null)
    } catch (err) {
      setUploadStatus('error')
      setUploadMessage(err.message || 'Could not reach the server.')
      setFileName('')
      setCandidate(null)
    }
  }

  async function handleAnalyze() {
    setAnalysisStatus('analyzing')
    setAnalysisMessage('')

    const formData = new FormData()
    if (jdInputMode === 'file' && jdFile) {
      formData.append('file', jdFile)
    } else {
      formData.append('job_description', jobDescription)
    }

    try {
      const response = await fetch(ANALYZE_URL, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` },
        body: formData,
      })
      const data = await response.json()

      if (!response.ok) {
        throw new Error(data.detail || 'Analysis failed.')
      }

      setAnalysisStatus('success')
      setAnalysis(data.analysis)
      setHistory(data.history || [])
    } catch (err) {
      setAnalysisStatus('error')
      setAnalysisMessage(err.message || 'Could not reach the server.')
      setAnalysis(null)
    }
  }

  function handleDrop(event) {
    event.preventDefault()
    setIsDragging(false)
    const file = event.dataTransfer.files?.[0]
    if (file) uploadFile(file)
  }

  function handleFileChange(event) {
    const file = event.target.files?.[0]
    if (file) uploadFile(file)
  }

  const canAnalyze = jdInputMode === 'text' ? Boolean(jobDescription.trim()) : Boolean(jdFile)

  return (
    <div className="page">
      <header className="app-header">
        <div className="brand">
          <BrandMark />
          <span className="brand-name">ResumeIQ</span>
        </div>
        <div className="header-user">
          <span className="top-bar-user">Signed in as <strong>{username}</strong></span>
          <button type="button" className="link-button" onClick={handleLogout}>
            Log out
          </button>
        </div>
      </header>

      <div className="hero">
        <p className="eyebrow">/ AI RESUME EVALUATOR</p>
        <h1>Score your resume against the job you want.</h1>
        <p className="subtitle">
          Upload your resume, add the job description, and get one score and
          recommendation that accounts for both resume quality and job fit.
        </p>
      </div>

      <section className="section">
        <h2 className="section-title"><span className="step-index">01</span> Upload Resume</h2>

        <div
          className={`dropzone ${isDragging ? 'dragging' : ''} ${uploadStatus}`}
          onClick={() => inputRef.current?.click()}
          onDragOver={(e) => {
            e.preventDefault()
            setIsDragging(true)
          }}
          onDragLeave={() => setIsDragging(false)}
          onDrop={handleDrop}
        >
          <input
            ref={inputRef}
            type="file"
            accept=".pdf,.docx"
            hidden
            onChange={handleFileChange}
          />
          <p className="dropzone-text">
            Drag & drop your resume here, or click to browse
          </p>
          <p className="dropzone-hint">PDF or DOCX, max {MAX_FILE_SIZE_MB}MB</p>
        </div>

        {uploadStatus === 'uploading' && <p className="status uploading">Uploading...</p>}
        {uploadStatus === 'success' && (
          <p className="status success">
            {uploadMessage} <strong>({fileName})</strong>
          </p>
        )}
        {uploadStatus === 'error' && <p className="status error">{uploadMessage}</p>}
      </section>

      {candidate && (
        <section className="section">
          <h2 className="section-title"><span className="step-index">02</span> Resume Information</h2>
          <div className="candidate-card">
            <p><strong>Name:</strong> {candidate.name || 'Not found'}</p>
            <p><strong>Email:</strong> {candidate.email || 'Not found'}</p>
            <p><strong>Phone:</strong> {candidate.phone || 'Not found'}</p>

            <p className="field-label"><strong>Skills</strong></p>
            {candidate.skills.length > 0 ? (
              <ul className="skill-list">
                {candidate.skills.map((skill) => (
                  <li key={skill}>{skill}</li>
                ))}
              </ul>
            ) : (
              <p className="not-found">Not found</p>
            )}

            <p className="field-label"><strong>Education</strong></p>
            {candidate.education.length > 0 ? (
              <ul>
                {candidate.education.map((entry, i) => (
                  <li key={i}>{entry}</li>
                ))}
              </ul>
            ) : (
              <p className="not-found">Not found</p>
            )}

            <p className="field-label"><strong>Experience</strong></p>
            {candidate.experience.length > 0 ? (
              <ul className="experience-list">
                {candidate.experience.map((exp, i) => (
                  <li key={i}>
                    <div className="experience-title">
                      {exp.title}
                      {exp.duration ? ` (${exp.duration})` : ''}
                    </div>
                    {exp.details.length > 0 && (
                      <ul>
                        {exp.details.map((detail, j) => (
                          <li key={j}>{detail}</li>
                        ))}
                      </ul>
                    )}
                  </li>
                ))}
              </ul>
            ) : (
              <p className="not-found">Not found</p>
            )}
          </div>
        </section>
      )}

      {candidate && (
        <section className="section">
          <h2 className="section-title"><span className="step-index">03</span> Add Job Description</h2>
          <div className="candidate-card">
            <p className="dropzone-hint" style={{ marginBottom: 10 }}>
              Paste the job description or upload it as a file, then analyze.
            </p>

            <div className="jd-mode-toggle">
              <button
                type="button"
                className={`jd-mode-button ${jdInputMode === 'text' ? 'active' : ''}`}
                onClick={() => setJdInputMode('text')}
              >
                Paste Text
              </button>
              <button
                type="button"
                className={`jd-mode-button ${jdInputMode === 'file' ? 'active' : ''}`}
                onClick={() => setJdInputMode('file')}
              >
                Upload File
              </button>
            </div>

            {jdInputMode === 'text' ? (
              <textarea
                className="job-description-input"
                placeholder="Paste the job description here..."
                value={jobDescription}
                onChange={(e) => setJobDescription(e.target.value)}
                rows={6}
              />
            ) : (
              <div
                className="dropzone jd-dropzone"
                onClick={() => jdFileRef.current?.click()}
              >
                <input
                  ref={jdFileRef}
                  type="file"
                  accept=".pdf,.docx,.txt"
                  hidden
                  onChange={(e) => setJdFile(e.target.files?.[0] || null)}
                />
                <p className="dropzone-text">
                  {jdFile ? jdFile.name : 'Click to upload the job description'}
                </p>
                <p className="dropzone-hint">PDF, DOCX, or TXT</p>
              </div>
            )}

            <button
              className="evaluate-button"
              disabled={!canAnalyze || analysisStatus === 'analyzing'}
              onClick={handleAnalyze}
            >
              {analysisStatus === 'analyzing' ? 'Analyzing...' : 'Analyze'}
            </button>
            {analysisStatus === 'error' && <p className="status error">{analysisMessage}</p>}
          </div>
        </section>
      )}

      {analysis && (
        <section className="section">
          <h2 className="section-title"><span className="step-index">04</span> Analysis Result</h2>
          <div className="evaluation-card">
            <div className="score-row">
              <div className="score-ring" style={{ '--score': analysis.overall_score }}>
                <div className="score-ring-inner">
                  <span className="score-number">{analysis.overall_score}</span>
                  <span className="score-max">/ 100</span>
                </div>
              </div>
              <div>
                <p className={`recommendation-badge ${RECOMMENDATION_CLASS[analysis.recommendation] || ''}`}>
                  {analysis.recommendation}
                </p>
                <p className="experience-level">{analysis.experience_level}</p>
              </div>
            </div>

            <div className="breakdown">
              <div className="breakdown-row">
                <span className="breakdown-label">resume quality</span>
                <div className="breakdown-track">
                  <div className="breakdown-fill" style={{ width: `${analysis.resume_quality_score}%` }} />
                </div>
                <span className="breakdown-value">{analysis.resume_quality_score}%</span>
              </div>
              <div className="breakdown-row">
                <span className="breakdown-label">job fit</span>
                <div className="breakdown-track">
                  <div className="breakdown-fill" style={{ width: `${analysis.job_fit_score}%` }} />
                </div>
                <span className="breakdown-value">{analysis.job_fit_score}%</span>
              </div>
            </div>

            <div className="eval-stats">
              <div>
                <span className="stat-value">{analysis.skills_count}</span>
                <span className="stat-label">Skills</span>
              </div>
              <div>
                <span className="stat-value">{analysis.total_experience_years}</span>
                <span className="stat-label">Years Experience</span>
              </div>
              <div>
                <span className="stat-value">{analysis.missing_sections.length}</span>
                <span className="stat-label">Missing Sections</span>
              </div>
            </div>

            {analysis.missing_sections.length > 0 && (
              <div className="field-label">
                <strong>Missing:</strong> {analysis.missing_sections.join(', ')}
              </div>
            )}

            <p className="field-label"><strong>Matched Skills</strong></p>
            {analysis.matched_skills.length > 0 ? (
              <ul className="skill-list">
                {analysis.matched_skills.map((skill) => (
                  <li key={skill}>{skill}</li>
                ))}
              </ul>
            ) : (
              <p className="not-found">None matched</p>
            )}

            <p className="field-label"><strong>Missing Skills</strong></p>
            {analysis.missing_skills.length > 0 ? (
              <ul className="skill-list skill-list-missing">
                {analysis.missing_skills.map((skill) => (
                  <li key={skill}>{skill}</li>
                ))}
              </ul>
            ) : (
              <p className="not-found">None &mdash; all required skills found</p>
            )}

            <p className="field-label">{analysis.experience_note}</p>
            <p className="field-label">{analysis.education_note}</p>

            <p className="field-label"><strong>Strengths</strong></p>
            {analysis.strengths.length > 0 ? (
              <ul>
                {analysis.strengths.map((item, i) => (
                  <li key={i}>{item}</li>
                ))}
              </ul>
            ) : (
              <p className="not-found">None identified</p>
            )}

            <p className="field-label"><strong>Suggestions</strong></p>
            <ul>
              {analysis.suggestions.map((item, i) => (
                <li key={i}>{item}</li>
              ))}
            </ul>
          </div>
        </section>
      )}

      {history.length > 0 && (
        <section className="section">
          <h2 className="section-title">
            <span className="step-index">05</span> Evaluation History
            <span className="section-title-hint">last {history.length}</span>
          </h2>
          <table className="history-table">
            <thead>
              <tr>
                <th>Name</th>
                <th>Score</th>
                <th>Recommendation</th>
                <th>Time</th>
              </tr>
            </thead>
            <tbody>
              {history.map((entry, i) => (
                <tr key={i}>
                  <td>{entry.name}</td>
                  <td>{entry.score}</td>
                  <td>{entry.recommendation}</td>
                  <td>{entry.evaluated_at}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      )}
    </div>
  )
}

export default App
