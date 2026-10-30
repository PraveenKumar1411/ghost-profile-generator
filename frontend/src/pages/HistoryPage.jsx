import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import TopBar from '../components/TopBar'
import { getApiErrorMessage, getScanHistory } from '../services/scanApi'

function riskClass(level) {
  return level === 'HIGH' ? 'history-risk-high' : level === 'MEDIUM' ? 'history-risk-medium' : 'history-risk-low'
}

function formatScanDate(value) {
  return new Intl.DateTimeFormat([], {
    dateStyle: 'medium',
    timeStyle: 'short',
  }).format(new Date(value))
}

export default function HistoryPage() {
  const [scans, setScans] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    let active = true
    getScanHistory()
      .then((data) => {
        if (active) setScans(data)
      })
      .catch((requestError) => {
        if (active) setError(getApiErrorMessage(requestError))
      })
      .finally(() => {
        if (active) setLoading(false)
      })

    return () => {
      active = false
    }
  }, [])

  const reportBaseUrl = import.meta.env.VITE_API_BASE_URL ?? 'http://127.0.0.1:8000/api/v1'

  return (
    <div className="app-shell history-shell">
      <TopBar />
      <main className="mx-auto w-full max-w-6xl px-5 pb-20 sm:px-8">
        <section className="history-header">
          <div>
            <p className="section-kicker">ghost intelligence / archive</p>
            <h1 className="history-title">Scan <span className="text-gradient">history</span></h1>
            <p className="history-subtitle">Review previous identity scans and revisit your exposure intelligence.</p>
          </div>
          <Link to="/" className="button-secondary">back to home <span>↗</span></Link>
        </section>

        <section className="history-content">
          <div className="history-section-heading">
            <div>
              <p className="section-kicker">saved intelligence</p>
              <h2 className="section-title mt-2">Recent scans</h2>
            </div>
            {!loading && !error && <span className="section-count">{scans.length} {scans.length === 1 ? 'scan' : 'scans'}</span>}
          </div>

          {loading && (
            <div className="history-state glass-card" aria-live="polite">
              <span className="history-loader" />
              <strong>Loading scan history</strong>
              <p>Retrieving your saved intelligence reports...</p>
            </div>
          )}

          {!loading && error && (
            <div className="history-state glass-card" role="alert">
              <span className="history-state-icon">!</span>
              <strong>History unavailable</strong>
              <p>{error}</p>
              <Link to="/" className="button-secondary">return home</Link>
            </div>
          )}

          {!loading && !error && scans.length === 0 && (
            <div className="history-state glass-card">
              <span className="history-state-icon">⌁</span>
              <strong>No scans yet</strong>
              <p>Run your first username scan to create a privacy intelligence report.</p>
              <Link to="/" className="button-primary">start a scan <span>→</span></Link>
            </div>
          )}

          {!loading && !error && scans.length > 0 && (
            <div className="history-list">
              {scans.map((scan, index) => (
                <article className="history-card glass-card" key={scan.id} style={{ '--history-delay': `${index * 70}ms` }}>
                  <div className="history-identity">
                    <span className="history-avatar">@</span>
                    <div><span className="history-label">Username</span><strong>@{scan.username}</strong></div>
                  </div>
                  <div className="history-detail"><span className="history-label">Risk score</span><strong className="history-score">{scan.risk_score}<small>/100</small></strong></div>
                  <div className="history-detail"><span className="history-label">Risk level</span><span className={`history-risk ${riskClass(scan.risk_level)}`}>{scan.risk_level}</span></div>
                  <div className="history-detail history-date"><span className="history-label">Scan date</span><strong>{formatScanDate(scan.created_at)}</strong></div>
                  <a className="history-report-button" href={`${reportBaseUrl}/report/${encodeURIComponent(scan.username)}`} target="_blank" rel="noreferrer">view report <span>↗</span></a>
                </article>
              ))}
            </div>
          )}
        </section>
      </main>
    </div>
  )
}
