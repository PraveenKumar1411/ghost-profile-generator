import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import TopBar from '../components/TopBar'
import { getAnalytics, getApiErrorMessage, getScanHistory } from '../services/scanApi'

function riskClass(level) {
  return level === 'CRITICAL' ? 'history-risk-critical' : level === 'HIGH' ? 'history-risk-high' : level === 'MEDIUM' ? 'history-risk-medium' : 'history-risk-low'
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
  const [analytics, setAnalytics] = useState(null)
  const [query, setQuery] = useState('')
  const [riskFilter, setRiskFilter] = useState('ALL')
  const [sortBy, setSortBy] = useState('recent')

  useEffect(() => {
    let active = true
    Promise.allSettled([getScanHistory(), getAnalytics()])
      .then(([historyResult, analyticsResult]) => {
        if (!active) return
        if (historyResult.status === 'fulfilled') setScans(historyResult.value)
        else setError(getApiErrorMessage(historyResult.reason))
        if (analyticsResult.status === 'fulfilled') setAnalytics(analyticsResult.value)
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
  const visibleScans = useMemo(() => scans
    .filter((scan) => scan.username.toLowerCase().includes(query.toLowerCase()))
    .filter((scan) => riskFilter === 'ALL' || scan.risk_level === riskFilter)
    .sort((a, b) => {
      if (sortBy === 'highest') return b.risk_score - a.risk_score
      if (sortBy === 'lowest') return a.risk_score - b.risk_score
      if (sortBy === 'oldest') return new Date(a.created_at) - new Date(b.created_at)
      return new Date(b.created_at) - new Date(a.created_at)
    }), [query, riskFilter, scans, sortBy])

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
            {!loading && !error && (
              <>
                <div className="analytics-grid">
                  <div className="analytics-card glass-card"><span>Total scans</span><strong>{analytics?.total_scans ?? scans.length}</strong></div>
                  <div className="analytics-card glass-card"><span>Highest risk</span><strong>{analytics?.highest_risk_score ?? 0}</strong></div>
                  <div className="analytics-card glass-card"><span>Average risk</span><strong>{analytics?.average_risk_score ?? 0}</strong></div>
                  <div className="analytics-card glass-card"><span>Common platform</span><strong>{analytics?.most_common_platform ?? '—'}</strong></div>
                </div>
                <div className="history-controls">
                  <input aria-label="Search scan history" placeholder="Search username" value={query} onChange={(event) => setQuery(event.target.value)} />
                  <select aria-label="Filter by risk" value={riskFilter} onChange={(event) => setRiskFilter(event.target.value)}>
                    <option value="ALL">All risk levels</option><option value="LOW">Low</option><option value="MEDIUM">Moderate</option><option value="HIGH">High</option><option value="CRITICAL">Critical</option>
                  </select>
                  <select aria-label="Sort scan history" value={sortBy} onChange={(event) => setSortBy(event.target.value)}>
                    <option value="recent">Most recent</option><option value="oldest">Oldest</option><option value="highest">Highest risk</option><option value="lowest">Lowest risk</option>
                  </select>
                </div>
              </>
            )}
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

          {!loading && !error && visibleScans.length > 0 && (
            <div className="history-list">
              {visibleScans.map((scan, index) => (
                <article className="history-card glass-card" key={scan.id} style={{ '--history-delay': `${index * 70}ms` }}>
                  <div className="history-identity">
                    <span className="history-avatar">@</span>
                    <div><span className="history-label">Username</span><strong>@{scan.username}</strong></div>
                  </div>
                  <div className="history-detail"><span className="history-label">Risk score</span><strong className="history-score">{scan.risk_score}<small>/100</small></strong></div>
                  <div className="history-detail"><span className="history-label">Risk level</span><span className={`history-risk ${riskClass(scan.risk_level)}`}>{scan.risk_level}</span><small className="history-grade">Grade {scan.privacy_grade}</small></div>
                  <div className="history-detail history-date"><span className="history-label">Scan date</span><strong>{formatScanDate(scan.created_at)}</strong></div>
                  <a className="history-report-button" href={`${reportBaseUrl}/report/id/${encodeURIComponent(scan.report_id)}`} target="_blank" rel="noreferrer">view report <span>↗</span></a>
                  <small className="history-report-id">{scan.report_id}</small>
                </article>
              ))}
            </div>
          )}
          {!loading && !error && scans.length > 0 && visibleScans.length === 0 && <div className="history-state glass-card"><span className="history-state-icon">⌕</span><strong>No matching scans</strong><p>Try a different search or filter.</p></div>}
        </section>
      </main>
    </div>
  )
}
