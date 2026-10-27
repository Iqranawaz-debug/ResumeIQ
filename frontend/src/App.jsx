import { useEffect, useRef, useState } from 'react'
import Auth from './Auth'
import BrandMark from './BrandMark'
import ThemeToggle from './ThemeToggle'
import PrintableReport from './PrintableReport'
import RecruiterWorkspace from './RecruiterWorkspace'
import ResultsDashboard from './ResultsDashboard'
import DocumentChecks from './DocumentChecks'
import PrivacyPanel from './PrivacyPanel'
import { initializeDraft, updateDraft } from './improvementState'
import './App.css'
import './dashboard.css'
import { API_BASE_URL, apiRequest, analysisForm } from './api'

const UPLOAD_URL = `${API_BASE_URL}/api/upload`
const ANALYZE_URL = `${API_BASE_URL}/api/analyze`
const HISTORY_URL = `${API_BASE_URL}/api/history`
const LOGOUT_URL = `${API_BASE_URL}/api/logout`
const ALLOWED_EXTENSIONS = ['pdf', 'docx']
const MAX_FILE_SIZE_MB = 10

const STEP_COPY = {
  1: { eyebrow: 'STEP 1 OF 4', title: 'Upload a resume', subtitle: "Bring a candidate's resume — we'll extract the key details." },
  2: { eyebrow: 'STEP 2 OF 4', title: 'Resume Information', subtitle: 'Review what we extracted before scoring.' },
  3: { eyebrow: 'STEP 3 OF 4', title: 'Add a job description', subtitle: 'Optional — add one for a job-fit score, or skip to evaluate the resume alone.' },
  4: { eyebrow: 'STEP 4 OF 4', title: 'Analysis Result', subtitle: 'Full breakdown, strengths, and recommendation.' },
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
  const [useAI, setUseAI] = useState(false)
  const [analysisStatus, setAnalysisStatus] = useState('idle') // idle | analyzing | success | error
  const [analysisMessage, setAnalysisMessage] = useState('')
  const [analysis, setAnalysis] = useState(null)
  const [improvements, setImprovements] = useState(null)
  const [improvementDraft, setImprovementDraft] = useState(null)
  const [improvementBusy, setImprovementBusy] = useState(false)
  const [improvementError, setImprovementError] = useState('')
  const improvementRequest = useRef(null)
  const [history, setHistory] = useState([])
  const [uploadedFile, setUploadedFile] = useState(null)
  const [historySearch, setHistorySearch] = useState('')

  const uploadRequest = useRef(null)
  const analysisRequest = useRef(null)
  const [resumeId, setResumeId] = useState(null)
  const [processingNote, setProcessingNote] = useState('')
  const [historyError, setHistoryError] = useState('')
  const inputRef = useRef(null)
  const jdFileRef = useRef(null)

  useEffect(() => () => improvementRequest.current?.abort(), [])

  function clearImprovements() {
    improvementRequest.current?.abort()
    improvementRequest.current = null
    setImprovements(null)
    setImprovementDraft(null)
    setImprovementBusy(false)
    setImprovementError('')
  }

  async function generateImprovements(useAI = false) {
    if (!resumeId || !analysis?.analysis_id) return
    improvementRequest.current?.abort()
    const controller = new AbortController()
    improvementRequest.current = controller
    setImprovementBusy(true)
    setImprovementError('')
    const body = new FormData()
    body.append('resume_id', resumeId)
    body.append('analysis_id', analysis.analysis_id)
    body.append('use_ai', String(Boolean(useAI)))
    try {
      const data = await apiRequest(`${API_BASE_URL}/api/improvements`, { method: 'POST', body,
        signal: controller.signal, headers: { Authorization: `Bearer ${token}` } })
      if (controller.signal.aborted || improvementRequest.current !== controller || data.resume_id !== resumeId || data.analysis_id !== analysis.analysis_id) return
      setImprovements(data.improvements)
      setImprovementDraft((previous) => initializeDraft(data.improvements, previous || {}))
    } catch (error) {
      if (!controller.signal.aborted && improvementRequest.current === controller) setImprovementError(error.message)
    } finally {
      if (!controller.signal.aborted && improvementRequest.current === controller) setImprovementBusy(false)
    }
  }

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme)
    localStorage.setItem('resumeiq_theme', theme)
  }, [theme])

  function toggleTheme() {
    setTheme((current) => (current === 'dark' ? 'light' : 'dark'))
  }

  useEffect(() => {
    if (!token) return
    const controller = new AbortController()
    setHistoryError('')
    apiRequest(HISTORY_URL, { signal: controller.signal, headers: { Authorization: `Bearer ${token}` } })
      .then((data) => { if (!controller.signal.aborted) setHistory(data.history || []) })
      .catch((error) => { if (!controller.signal.aborted) setHistoryError(error.message) })
    const expired = (event) => {
      if (event.detail === `Bearer ${token}`) clearSession()
    }
    window.addEventListener('resumeiq-session-expired', expired)
    return () => {
      controller.abort()
      window.removeEventListener('resumeiq-session-expired', expired)
    }
  }, [token])

  function handleAuthSuccess(newToken, newUsername) {
    localStorage.setItem('resumeiq_token', newToken)
    localStorage.setItem('resumeiq_username', newUsername)
    setToken(newToken)
    setUsername(newUsername)
  }

  async function handleLogout() {
    clearImprovements()
    uploadRequest.current?.abort()
    analysisRequest.current?.abort()
    try {
      await apiRequest(LOGOUT_URL, { method: 'POST', timeoutMs: 10000, headers: { Authorization: `Bearer ${token}` } })
    } catch {
      // Local sign-out still completes; server token expires if revocation could not arrive.
    }
    clearSession()
  }

  function clearSession() {
    clearImprovements()
    uploadRequest.current?.abort()
    analysisRequest.current?.abort()
    setResumeId(null)
    setProcessingNote('')
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
    uploadRequest.current?.abort()
    analysisRequest.current?.abort()
    const controller = new AbortController()
    uploadRequest.current = controller
    setAnalysisStatus('idle')
    const clientError = validateFile(file)
    if (clientError) {
      setUploadStatus('error')
      setUploadMessage(clientError)
      return
    }

    setUploadStatus('uploading')
    setUploadMessage('')

    const formData = new FormData()
    formData.append('file', file)

    try {
      const data = await apiRequest(UPLOAD_URL, {
        signal: controller.signal,
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` },
        body: formData,
      })
      if (controller.signal.aborted || uploadRequest.current !== controller) return
      clearImprovements()
      setAnalysis(null)
      setResumeId(data.resume_id)
      setProcessingNote(`Skill categorization: ${data.categorization_method}. ${data.processing_note || ''}`)
      setUploadStatus('success')
      setUploadMessage(data.message)
      setFileName(data.filename)
      setCandidate(data.candidate || null)
      setUploadedFile(file)
    } catch (err) {
      if (controller.signal.aborted || uploadRequest.current !== controller) return
      setUploadStatus('error')
      setUploadMessage(err.message || 'Could not reach the server.')
    }
  }

  async function handleAnalyze() {
    clearImprovements()
    analysisRequest.current?.abort()
    const controller = new AbortController()
    analysisRequest.current = controller
    setAnalysisStatus('analyzing')
    setAnalysisMessage('')

    const formData = analysisForm(jdInputMode, jobDescription, jdFile, resumeId, useAI)

    try {
      const data = await apiRequest(ANALYZE_URL, {
        signal: controller.signal,
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` },
        body: formData,
      })
      if (controller.signal.aborted || analysisRequest.current !== controller) return
      if (!Number.isFinite(data.analysis?.overall_score)) {
        throw new Error('Server returned an incomplete analysis. Please retry.')
      }
      setAnalysisStatus('success')
      setAnalysis(data.analysis)
      setHistory(data.history || [])
      setCurrentStep(4)
    } catch (err) {
      if (controller.signal.aborted || analysisRequest.current !== controller) return
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
      if (Number.isFinite(analysis.local_overall_score) && analysis.job_fit_method === 'ai') {
        lines.push(`Local rules (for comparison): ${analysis.local_overall_score} / 100; job fit ${analysis.local_job_fit_score} / 100 - ${analysis.local_job_fit_label}`)
      }
      if (analysis.matched_skills.length > 0) {
        lines.push('', analysis.job_fit_method === 'ai' ? 'PROVIDER-REPORTED MATCHES (UNVERIFIED)' : 'MATCHED SKILLS', ...analysis.matched_skills.map((s) => `- ${s}`))
      }
      if (analysis.missing_skills.length > 0) {
        lines.push('', 'REQUIREMENTS NOT EVIDENCED', ...analysis.missing_skills.map((s) => `- ${s}`))
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

    const requirementRows = analysis.explanation?.requirement_lines?.rows || []
    if (requirementRows.length) {
      lines.push('', 'REQUIREMENT REVIEW (display only; does not change the score)')
      for (const row of requirementRows) lines.push(`[${row.status}] ${row.text} - ${row.reason}`)
    }
    const findings = candidate.document_checks?.findings || []
    if (findings.length) lines.push('', 'DOCUMENT READABILITY', ...findings.map((item) => `[${item.severity}] ${item.title}: ${item.fix}`))

    if (analysis.explanation) {
      lines.push('', 'SCORE EXPLANATION', analysis.explanation.summary, analysis.explanation.advisory)
      if (analysis.explanation.job_rule) lines.push(analysis.explanation.job_rule)
      for (const requirement of analysis.explanation.requirements || []) {
        lines.push(`${requirement.skill}: ${requirement.status === 'matched' ? 'Listed skill match' : 'Not evidenced in resume'}`)
        for (const evidence of requirement.evidence || []) lines.push(`${evidence.section}: "${evidence.excerpt}"`)
      }
      lines.push('', 'RECOMMENDED IMPROVEMENTS', ...(analysis.explanation.recommendations || []))
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
    clearImprovements()
    uploadRequest.current?.abort()
    analysisRequest.current?.abort()
    setResumeId(null)
    setProcessingNote('')
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
          <button type="button" className={`sidebar-nav-item ${activePage === 'recruiter' ? 'active' : ''}`} onClick={() => setActivePage('recruiter')}>Recruitment</button>
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
          <button type="button" className={`sidebar-nav-item ${activePage === 'privacy' ? 'active' : ''}`} onClick={() => setActivePage('privacy')}>
            Privacy &amp; data
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
        {activePage === 'recruiter' && <RecruiterWorkspace key={token} token={token} />}
        {activePage === 'upload' && (
          <div className={`wizard ${currentStep === 4 ? 'wizard-wide' : ''}`}>
            <p className="eyebrow">{step.eyebrow}</p>
            <h1>{step.title}</h1>
            <p className="subtitle">{step.subtitle}</p>

            {currentStep === 1 && (
              <div className="wizard-panel">
                <div
                  className={`dropzone dropzone-hero ${isDragging ? 'dragging' : ''} ${uploadStatus}`}
                  role="button"
                  tabIndex={0}
                  aria-label="Upload resume file"
                  onKeyDown={(event) => {
                    if (event.target === event.currentTarget && (event.key === 'Enter' || event.key === ' ')) {
                      event.preventDefault()
                      inputRef.current?.click()
                    }
                  }}
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

                <p className="wizard-note">The file itself is not kept. Extracted details and results stay in server memory and are erased after a period of inactivity, on restart, or when you delete them under Privacy &amp; data.</p>

                <div className="wizard-actions">
                  <button
                    type="button"
                    className="evaluate-button"
                    disabled={!candidate || uploadStatus === 'uploading'}
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
                  <p className="field-label" role="status">{processingNote}</p>
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

                  <p className="field-label"><strong>Professional Experience</strong></p>
                  {(candidate.experience || []).length > 0 ? (
                    <ul className="experience-list">
                      {candidate.experience.map((exp, i) => (
                        <li key={i}>
                          <div className="experience-title">
                            {exp.title || 'Position not specified'}
                            {exp.organization ? ` — ${exp.organization}` : ''}
                            {exp.duration ? ` (${exp.duration})` : ''}
                          </div>
                          {(exp.header_lines || []).map((line, j) => <p key={`header-${j}`}>{line}</p>)}
                          {exp.date_status === 'invalid' && <p className="field-label">Date range needs review</p>}
                          {(exp.details || []).length > 0 && (
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
                  <p className="field-label"><strong>Projects &amp; Open Source</strong></p>
                  {(candidate.projects || []).length > 0 ? (
                    <ul className="experience-list">
                      {candidate.projects.map((project, i) => (
                        <li key={i}>
                          {project.title && <div className="experience-title">{project.title}</div>}
                          {(project.details || []).length > 0 && (
                            <ul>{project.details.map((detail, j) => <li key={j}>{detail}</li>)}</ul>
                          )}
                        </li>
                      ))}
                    </ul>
                  ) : <p className="not-found">Not found</p>}
                </div>

                <DocumentChecks checks={candidate.document_checks} compact />

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
                      aria-label="Job description"
                      className="job-description-input"
                      placeholder="Paste the job description here..."
                      value={jobDescription}
                      onChange={(e) => setJobDescription(e.target.value)}
                      rows={6}
                    />
                  ) : (
                    <div
                      className="dropzone jd-dropzone"
                      role="button"
                      tabIndex={0}
                      aria-label="Upload job description file"
                      onKeyDown={(event) => {
                        if (event.target === event.currentTarget && (event.key === 'Enter' || event.key === ' ')) {
                          event.preventDefault()
                          jdFileRef.current?.click()
                        }
                      }}
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

                  {hasJobDescription && (
                    <>
                      <label className="ai-opt-in">
                        <input type="checkbox" checked={useAI} onChange={(e) => setUseAI(e.target.checked)} />
                        Use AI job matching
                      </label>
                      <p className="wizard-note">
                        When checked, extracted skills, education and employment details (with best-effort contact redaction) and the job description are sent to the configured AI provider. If it is unavailable, local matching is used.
                      </p>
                    </>
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
                <ResultsDashboard key={analysis.analysis_id} analysis={analysis} candidate={candidate}
                  improvements={improvements} improvementDraft={improvementDraft}
                  improvementBusy={improvementBusy} improvementError={improvementError}
                  canGenerate={Boolean(resumeId && analysis.analysis_id)} onGenerate={generateImprovements}
                  onAction={(action) => setImprovementDraft((draft) => updateDraft(improvements, draft, action))}
                  onDownload={handleDownloadRecommendation} />

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

        {activePage === 'privacy' && (
          <div className="wizard">
            <p className="eyebrow">/ PRIVACY</p>
            <h1>Privacy &amp; data</h1>
            <p className="subtitle">Exactly what is held for your account, and a way to erase it.</p>
            <PrivacyPanel key={token} token={token} onDeleted={() => { handleStartOver(); setHistory([]) }} />
          </div>
        )}

        {activePage === 'history' && (
          <div className="wizard">
            <p className="eyebrow">/ HISTORY</p>
            <h1>Evaluation History</h1>
            {historyError && <p className="status error" role="alert">{historyError}</p>}
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

      <PrintableReport candidate={candidate} analysis={analysis} improvements={improvements} improvementDraft={improvementDraft} />
    </div>
  )
}

export default App
