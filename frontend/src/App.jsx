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
const STATS_URL = `${API_BASE_URL}/api/stats`
const LOGOUT_URL = `${API_BASE_URL}/api/logout`
const ALLOWED_EXTENSIONS = ['pdf', 'docx']
const MAX_FILE_SIZE_MB = 10

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

const SKILL_CLOUD_MIN_SIZE = 14
const SKILL_CLOUD_MAX_SIZE = 38

function getSkillCloudSizes(skillCloud) {
  const counts = Object.values(skillCloud)
  const min = Math.min(...counts)
  const max = Math.max(...counts)
  const sizes = {}
  for (const [skill, count] of Object.entries(skillCloud)) {
    sizes[skill] =
      max === min
        ? (SKILL_CLOUD_MIN_SIZE + SKILL_CLOUD_MAX_SIZE) / 2
        : SKILL_CLOUD_MIN_SIZE +
          ((count - min) / (max - min)) * (SKILL_CLOUD_MAX_SIZE - SKILL_CLOUD_MIN_SIZE)
  }
  return sizes
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
  const [theme, setTheme] = useState(() => localStorage.getItem('resumeiq_theme') || 'dark')

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
  const [stats, setStats] = useState(null)
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

    fetch(STATS_URL, { headers: { Authorization: `Bearer ${token}` } })
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => setStats(data))
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
    setStats(null)
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
      setStats(data.stats || null)
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

  const hasJobDescription = jdInputMode === 'text' ? Boolean(jobDescription.trim()) : Boolean(jdFile)

  const filteredHistory = history.filter((entry) =>
    (entry.name || '').toLowerCase().includes(historySearch.trim().toLowerCase())
  )

  return (
    <div className="page">
      <header className="app-header">
        <div className="brand">
          <BrandMark />
          <span className="brand-name">ResumeIQ</span>
        </div>
        <div className="header-user">
          <ThemeToggle theme={theme} onToggle={toggleTheme} />
          <span className="top-bar-user">Signed in as <strong>{username}</strong></span>
          <button type="button" className="link-button" onClick={handleLogout}>
            Log out
          </button>
        </div>
      </header>

      <div className="hero">
        <p className="eyebrow">/ AI RESUME EVALUATOR</p>
        <h1>Score candidate resumes against your job requirements.</h1>
        <p className="subtitle">
          Upload a candidate's resume, add the job description, and get one score
          and hiring recommendation that accounts for both resume quality and job fit.
        </p>
      </div>

      {stats && stats.total_resumes > 0 && (
        <section className="section">
          <h2 className="section-title">Today's Evaluations</h2>
          <div className="stats-grid">
            <div className="stat-card">
              <span className="stat-card-value">{stats.total_resumes}</span>
              <span className="stat-card-label">Total Resumes</span>
            </div>
            <div className="stat-card">
              <span className="stat-card-value">{stats.recommended}</span>
              <span className="stat-card-label">Recommended</span>
            </div>
            <div className="stat-card">
              <span className="stat-card-value">{stats.rejected}</span>
              <span className="stat-card-label">Rejected</span>
            </div>
            <div className="stat-card">
              <span className="stat-card-value">{stats.average_score}</span>
              <span className="stat-card-label">Average Score</span>
            </div>
            <div className="stat-card">
              <span className="stat-card-value">{stats.top_skill || '—'}</span>
              <span className="stat-card-label">Top Skill</span>
            </div>
          </div>
        </section>
      )}

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
          <h2 className="section-title">
            <span className="step-index">02</span> Resume Information
            {uploadedFile && (
              <button
                type="button"
                className="link-button section-action"
                onClick={handleViewResume}
              >
                View Uploaded File
              </button>
            )}
          </h2>
          <div className="candidate-card">
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

            {candidate.skill_cloud && Object.keys(candidate.skill_cloud).length > 0 && (
              <>
                <p className="field-label"><strong>Skill Cloud</strong></p>
                <div className="skill-cloud">
                  {Object.entries(getSkillCloudSizes(candidate.skill_cloud)).map(([skill, size]) => (
                    <span key={skill} className="skill-cloud-word" style={{ fontSize: `${size}px` }}>
                      {skill}
                    </span>
                  ))}
                </div>
              </>
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
          <h2 className="section-title">
            <span className="step-index">03</span> Add Job Description
            <span className="section-title-hint">optional</span>
          </h2>
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
            {analysisStatus === 'error' && <p className="status error">{analysisMessage}</p>}
          </div>
        </section>
      )}

      {analysis && (
        <section className="section">
          <h2 className="section-title">
            <span className="step-index">04</span> Analysis Result
            <button
              type="button"
              className="link-button section-action"
              onClick={handleDownloadRecommendation}
            >
              Download Recommendation
            </button>
          </h2>
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
                        <th>Basis</th>
                        <th>Score</th>
                        <th>Result</th>
                      </tr>
                    </thead>
                    <tbody>
                      <tr>
                        <td>Resume only</td>
                        <td>{analysis.resume_quality_score} / 100</td>
                        <td>{analysis.resume_only_recommendation}</td>
                      </tr>
                      <tr>
                        <td>Job description match</td>
                        <td>{analysis.job_fit_score} / 100</td>
                        <td>{analysis.job_fit_label}</td>
                      </tr>
                      <tr>
                        <td>Combined (overall)</td>
                        <td>{analysis.overall_score} / 100</td>
                        <td>{analysis.recommendation}</td>
                      </tr>
                    </tbody>
                  </table>
                </div>
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
        </section>
      )}

      {history.length > 0 && (
        <section className="section">
          <h2 className="section-title">
            <span className="step-index">05</span> Evaluation History
            <span className="section-title-hint">last {history.length}</span>
          </h2>
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
        </section>
      )}

      <PrintableReport candidate={candidate} analysis={analysis} />
    </div>
  )
}

export default App
