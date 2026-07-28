import { useEffect, useRef, useState } from 'react'
import Auth from './Auth'
import BrandMark from './BrandMark'
import ThemeToggle from './ThemeToggle'
import PrintableReport from './PrintableReport'
import './App.css'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8001'
const UPLOAD_URL = `${API_BASE_URL}/api/upload`
const ANALYZE_URL = `${API_BASE_URL}/api/analyze`
const HISTORY_URL = `${API_BASE_URL}/api/history`
const LOGOUT_URL = `${API_BASE_URL}/api/logout`
const ALLOWED_EXTENSIONS = ['pdf', 'docx']
const MAX_FILE_SIZE_MB = 10
const TOTAL_STEPS = 4

const STEP_COPY = {
  1: { eyebrow: 'STEP 1 OF 4', title: 'Upload a resume', subtitle: "Bring a candidate's resume — we'll extract the key details." },
  2: { eyebrow: 'STEP 2 OF 4', title: 'Resume Information', subtitle: 'Review what we extracted before scoring.' },
  3: { eyebrow: 'STEP 3 OF 4', title: 'Add a job description', subtitle: 'Optional — add one for a job-fit score, or skip to evaluate the resume alone.' },
  4: { eyebrow: 'STEP 4 OF 4', title: 'Analysis Result', subtitle: 'Full breakdown, strengths, and recommendation.' },
}

const RECOMMENDATION_CLASS = {
  'Highly Recommended': 'rec-highly',
  Recommended: 'rec-recommended',
  Consider: 'rec-consider',
  'Not Recommended': 'rec-not',
}

const RADAR_LABELS = [
  { key: 'technical_skills', label: 'Technical Skills' },
  { key: 'communication', label: 'Communication' },
  { key: 'projects', label: 'Projects' },
  { key: 'experience', label: 'Experience' },
  { key: 'education', label: 'Education' },
]

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
  const [theme, setTheme] = useState(() => localStorage.getItem('resumeiq_theme') || 'light')

  const [activePage, setActivePage] = useState('upload') // upload | history
  const [currentStep, setCurrentStep] = useState(1)

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
  const [uploadedFile, setUploadedFile] = useState(null)
  const [historySearch, setHistorySearch] = useState('')

  const inputRef = useRef(null)
  const jdFileRef = useRef(null)

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme)
    localStorage.setItem('resumeiq_theme', theme)
  }, [theme])

  function toggleTheme() {
    setTheme((current) => (current === 'dark' ? 'light' : 'dark'))
  }

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
    setActivePage('upload')
    setCurrentStep(1)
    setUploadStatus('idle')
    setCandidate(null)
    setAnalysis(null)
    setAnalysisStatus('idle')
    setHistory([])
    setJobDescription('')
    setJdFile(null)
    setUploadedFile(null)
    setHistorySearch('')
  }

  if (!token) {
    return <Auth theme={theme} onToggleTheme={toggleTheme} onAuthSuccess={handleAuthSuccess} />
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
      setUploadedFile(null)
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
      setUploadedFile(file)
    } catch (err) {
      setUploadStatus('error')
      setUploadMessage(err.message || 'Could not reach the server.')
      setFileName('')
      setCandidate(null)
      setUploadedFile(null)
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
      setCurrentStep(4)
    } catch (err) {
      setAnalysisStatus('error')
      setAnalysisMessage(err.message || 'Could not reach the server.')
      setAnalysis(null)
    }
  }

  function handleViewResume() {
    if (!uploadedFile) return
    const url = URL.createObjectURL(uploadedFile)
    window.open(url, '_blank', 'noopener')
    setTimeout(() => URL.revokeObjectURL(url), 60000)
  }

  function handleDownloadRecommendation() {
    if (!candidate || !analysis) return

    const lines = [
      'ResumeIQ - Candidate Evaluation Report',
      `Generated: ${new Date().toLocaleString()}`,
      '',
      'CANDIDATE',
      `Name: ${candidate.name || 'Not found'}`,
      `Email: ${candidate.email || 'Not found'}`,
      `Phone: ${candidate.phone || 'Not found'}`,
      '',
      'SCORE & RECOMMENDATION',
      `Overall Score: ${analysis.overall_score} / 100`,
      `Recommendation: ${analysis.recommendation}`,
      `Experience Level: ${analysis.experience_level}`,
      `Years of Experience: ${analysis.total_experience_years}`,
      `Skills Identified: ${analysis.skills_count}`,
    ]

    if (analysis.missing_sections.length > 0) {
      lines.push(`Missing Sections: ${analysis.missing_sections.join(', ')}`)
    }

    if (analysis.job_fit_score !== null && analysis.job_fit_score !== undefined) {
      lines.push(
        '',
        'SCORE COMPARISON',
        `Resume Only: ${analysis.resume_quality_score} / 100 - ${analysis.resume_only_recommendation}`,
        `Job Description Match: ${analysis.job_fit_score} / 100 - ${analysis.job_fit_label}`,
        `Combined (Overall): ${analysis.overall_score} / 100 - ${analysis.recommendation}`,
      )
      if (analysis.matched_skills.length > 0) {
        lines.push('', 'MATCHED SKILLS', ...analysis.matched_skills.map((s) => `- ${s}`))
      }
      if (analysis.missing_skills.length > 0) {
        lines.push('', 'MISSING SKILLS', ...analysis.missing_skills.map((s) => `- ${s}`))
      }
    }

    if (candidate.skills.length > 0) {
      lines.push('', 'SKILLS', ...candidate.skills.map((s) => `- ${s}`))
    }
    if (analysis.strengths.length > 0) {
      lines.push('', 'STRENGTHS', ...analysis.strengths.map((s) => `- ${s}`))
    }
    if (analysis.suggestions.length > 0) {
      lines.push('', 'SUGGESTIONS', ...analysis.suggestions.map((s) => `- ${s}`))
    }

    const blob = new Blob([lines.join('\n')], { type: 'text/plain' })
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = `${(candidate.name || 'candidate').replace(/\s+/g, '_')}_evaluation.txt`
    document.body.appendChild(link)
    link.click()
    link.remove()
    URL.revokeObjectURL(url)
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

  function handleStartOver() {
    setCurrentStep(1)
    setUploadStatus('idle')
    setUploadMessage('')
    setFileName('')
    setCandidate(null)
    setUploadedFile(null)
    setJobDescription('')
    setJdFile(null)
    setAnalysis(null)
    setAnalysisStatus('idle')
    setAnalysisMessage('')
  }

  const hasJobDescription = jdInputMode === 'text' ? Boolean(jobDescription.trim()) : Boolean(jdFile)

  const filteredHistory = history.filter((entry) =>
    (entry.name || '').toLowerCase().includes(historySearch.trim().toLowerCase())
  )

  const step = STEP_COPY[currentStep]

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="sidebar-brand">
          <BrandMark />
          <div className="sidebar-brand-text">
            <span className="sidebar-brand-name">ResumeIQ</span>
            <span className="sidebar-brand-tag">Recruiter workspace</span>
          </div>
          <ThemeToggle theme={theme} onToggle={toggleTheme} />
        </div>

        <nav className="sidebar-nav">
          <button
            type="button"
            className={`sidebar-nav-item ${activePage === 'upload' ? 'active' : ''}`}
            onClick={() => setActivePage('upload')}
          >
            Upload
          </button>
          <button
            type="button"
            className={`sidebar-nav-item ${activePage === 'history' ? 'active' : ''}`}
            onClick={() => setActivePage('history')}
          >
            History
          </button>
        </nav>

        <div className="sidebar-footer">
          <span className="sidebar-user-email">{username}</span>
          <button type="button" className="link-button" onClick={handleLogout}>
            Log out
          </button>
        </div>
      </aside>

      <main className="main-content">
        {activePage === 'upload' && (
          <div className="wizard">
            <p className="eyebrow">{step.eyebrow}</p>
            <h1>{step.title}</h1>
            <p className="subtitle">{step.subtitle}</p>

            {currentStep === 1 && (
              <div className="wizard-panel">
                <div
                  className={`dropzone dropzone-hero ${isDragging ? 'dragging' : ''} ${uploadStatus}`}
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
                  <span className="dropzone-icon">⬆</span>
                  <p className="dropzone-text">
                    Drag &amp; drop a resume here, or <span className="dropzone-link">browse files</span>
                  </p>
                  <p className="dropzone-hint">PDF or DOCX, up to {MAX_FILE_SIZE_MB}MB</p>
                </div>

                {uploadStatus === 'uploading' && <p className="status uploading">Uploading...</p>}
                {uploadStatus === 'success' && (
                  <p className="status success">
                    {uploadMessage} <strong>({fileName})</strong>
                  </p>
                )}
                {uploadStatus === 'error' && <p className="status error">{uploadMessage}</p>}

                <p className="wizard-note">We only read the file to extract text — nothing is stored beyond this session.</p>

                <div className="wizard-actions">
                  <button
                    type="button"
                    className="evaluate-button"
                    disabled={!candidate}
                    onClick={() => setCurrentStep(2)}
                  >
                    Continue
                  </button>
                </div>
              </div>
            )}

            {currentStep === 2 && candidate && (
              <div className="wizard-panel">
                <div className="candidate-card">
                  <div className="candidate-card-header">
                    {uploadedFile && (
                      <button type="button" className="link-button" onClick={handleViewResume}>
                        View Uploaded File
                      </button>
                    )}
                  </div>
                  <p><strong>Name:</strong> {candidate.name || 'Not found'}</p>
                  <p><strong>Email:</strong> {candidate.email || 'Not found'}</p>
                  <p><strong>Phone:</strong> {candidate.phone || 'Not found'}</p>

                  <p className="field-label"><strong>Skills</strong></p>
                  {candidate.skills.length > 0 ? (
                    candidate.skills_by_category ? (
                      <div className="skill-categories">
                        {Object.entries(candidate.skills_by_category).map(([category, skills]) => (
                          <div className="skill-category" key={category}>
                            <p className="skill-category-title">{category}</p>
                            <ul className="skill-list">
                              {skills.map((skill) => (
                                <li key={skill}>{skill}</li>
                              ))}
                            </ul>
                          </div>
                        ))}
                      </div>
                    ) : (
                      <ul className="skill-list">
                        {candidate.skills.map((skill) => (
                          <li key={skill}>{skill}</li>
                        ))}
                      </ul>
                    )
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

                <div className="wizard-actions">
                  <button type="button" className="link-button" onClick={() => setCurrentStep(1)}>
                    Back
                  </button>
                  <button type="button" className="evaluate-button" onClick={() => setCurrentStep(3)}>
                    Continue
                  </button>
                </div>
              </div>
            )}

            {currentStep === 3 && candidate && (
              <div className="wizard-panel">
                <div className="candidate-card">
                  <p className="dropzone-hint" style={{ marginBottom: 10 }}>
                    Add a job description to also get a job-fit score against a specific
                    role — or skip it and evaluate the resume on its own.
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

                  {analysisStatus === 'error' && <p className="status error">{analysisMessage}</p>}
                </div>

                <div className="wizard-actions">
                  <button type="button" className="link-button" onClick={() => setCurrentStep(2)}>
                    Back
                  </button>
                  <button
                    className="evaluate-button"
                    disabled={analysisStatus === 'analyzing'}
                    onClick={handleAnalyze}
                  >
                    {analysisStatus === 'analyzing'
                      ? 'Analyzing...'
                      : hasJobDescription
                        ? 'Analyze Against Job Description'
                        : 'Evaluate Resume Only'}
                  </button>
                </div>
              </div>
            )}

            {currentStep === 4 && analysis && (
              <div className="wizard-panel">
                <div className="evaluation-card">
                  <div className="candidate-card-header">
                    <button type="button" className="link-button" onClick={handleDownloadRecommendation}>
                      Download Recommendation
                    </button>
                  </div>
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

                  {analysis.job_fit_score !== null && analysis.job_fit_score !== undefined && (
                    <>
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

                      <p className="field-label"><strong>Score Comparison</strong></p>
                      <div className="table-scroll">
                        <table className="history-table comparison-table">
                          <thead>
                            <tr>
                              <th>Score Type</th>
                              <th>Score</th>
                              <th>Verdict</th>
                            </tr>
                          </thead>
                          <tbody>
                            <tr>
                              <td>Resume Quality</td>
                              <td>{analysis.resume_quality_score} / 100</td>
                              <td>{analysis.resume_only_recommendation}</td>
                            </tr>
                            <tr>
                              <td>Job Description Match</td>
                              <td>{analysis.job_fit_score} / 100</td>
                              <td>{analysis.job_fit_label}</td>
                            </tr>
                            <tr className="comparison-final-row">
                              <td>Overall Score</td>
                              <td>{analysis.overall_score} / 100</td>
                              <td>{analysis.recommendation}</td>
                            </tr>
                          </tbody>
                        </table>
                      </div>
                      <p className="comparison-formula">
                        Overall Score = Resume Quality (30%) + Job Description Match (70%)
                      </p>
                    </>
                  )}

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

                  {analysis.job_fit_score !== null && analysis.job_fit_score !== undefined && (
                    <>
                      {analysis.matched_skills.length === 0 && analysis.missing_skills.length === 0 ? (
                        <>
                          <p className="field-label"><strong>Skill Match</strong></p>
                          <p className="not-found">
                            No specific skills could be identified in this job description to compare
                            against the resume.
                          </p>
                        </>
                      ) : (
                        <>
                          <p className="field-label"><strong>Matched Skills</strong></p>
                          {analysis.matched_skills.length > 0 ? (
                            <ul className="skill-list">
                              {analysis.matched_skills.map((skill) => (
                                <li key={skill}>{skill}</li>
                              ))}
                            </ul>
                          ) : (
                            <p className="not-found">None of the required skills were found on the resume</p>
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
                        </>
                      )}

                      <p className="field-label">{analysis.experience_note}</p>
                      <p className="field-label">{analysis.education_note}</p>
                    </>
                  )}

                  {analysis.radar && (
                    <>
                      <p className="field-label"><strong>Candidate Strength Radar</strong></p>
                      <div className="breakdown radar-breakdown">
                        {RADAR_LABELS.map(({ key, label }) => (
                          <div className="breakdown-row" key={key}>
                            <span className="breakdown-label">{label}</span>
                            <div className="breakdown-track">
                              <div className="breakdown-fill" style={{ width: `${analysis.radar[key]}%` }} />
                            </div>
                            <span className="breakdown-value">{analysis.radar[key]}%</span>
                          </div>
                        ))}
                      </div>
                    </>
                  )}

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

                  <p className="field-label"><strong>Weaknesses</strong></p>
                  {analysis.weaknesses && analysis.weaknesses.length > 0 ? (
                    <ul>
                      {analysis.weaknesses.map((item, i) => (
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

                  <p className="field-label"><strong>Suggested Interview Questions</strong></p>
                  {analysis.interview_questions && analysis.interview_questions.length > 0 ? (
                    <ol>
                      {analysis.interview_questions.map((item, i) => (
                        <li key={i}>{item}</li>
                      ))}
                    </ol>
                  ) : (
                    <p className="not-found">None generated</p>
                  )}

                  <button type="button" className="evaluate-button print-report-button" onClick={() => window.print()}>
                    Generate Full Report (PDF)
                  </button>
                </div>

                <div className="wizard-actions">
                  <button type="button" className="link-button" onClick={() => setCurrentStep(3)}>
                    Back
                  </button>
                  <button type="button" className="evaluate-button" onClick={handleStartOver}>
                    Evaluate Another Resume
                  </button>
                </div>
              </div>
            )}
          </div>
        )}

        {activePage === 'history' && (
          <div className="wizard">
            <p className="eyebrow">/ HISTORY</p>
            <h1>Evaluation History</h1>
            <p className="subtitle">Your last {history.length} evaluation{history.length === 1 ? '' : 's'}.</p>

            {history.length > 0 ? (
              <>
                <input
                  type="text"
                  className="history-search"
                  placeholder="Search by candidate name..."
                  value={historySearch}
                  onChange={(e) => setHistorySearch(e.target.value)}
                />
                <div className="table-scroll">
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
                      {filteredHistory.length > 0 ? (
                        filteredHistory.map((entry, i) => (
                          <tr key={i}>
                            <td>{entry.name}</td>
                            <td>{entry.score}</td>
                            <td>{entry.recommendation}</td>
                            <td>{entry.evaluated_at}</td>
                          </tr>
                        ))
                      ) : (
                        <tr>
                          <td colSpan={4} className="not-found">
                            No evaluations match "{historySearch}"
                          </td>
                        </tr>
                      )}
                    </tbody>
                  </table>
                </div>
              </>
            ) : (
              <p className="not-found">No evaluations yet — head to Upload to get started.</p>
            )}
          </div>
        )}
      </main>

      <PrintableReport candidate={candidate} analysis={analysis} />
    </div>
  )
}

export default App
