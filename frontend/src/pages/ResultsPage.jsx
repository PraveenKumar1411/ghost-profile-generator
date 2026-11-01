import { useEffect, useState } from 'react'
import { Navigate, useLocation } from 'react-router-dom'
import TopBar from '../components/TopBar'
import PlatformCard from '../components/PlatformCard'
import ExposureCharts from '../components/ExposureCharts'
import SystemStatusPanel from '../components/SystemStatusPanel'
import { downloadReport, getApiErrorMessage } from '../services/scanApi'

const PLATFORMS = ['github', 'reddit', 'twitter', 'instagram', 'linkedin', 'facebook', 'youtube', 'tiktok', 'threads', 'telegram']
const PLATFORM_LABELS = {
  github: 'GitHub',
  reddit: 'Reddit',
  twitter: 'Twitter / X',
  instagram: 'Instagram',
  linkedin: 'LinkedIn',
  facebook: 'Facebook',
  youtube: 'YouTube',
  tiktok: 'TikTok',
  threads: 'Threads',
  telegram: 'Telegram',
}
const PLATFORM_WEIGHTS = Object.fromEntries(PLATFORMS.map((platform) => [platform, 10]))
const FALLBACK_RECOMMENDATIONS = [
  { title: 'Enable MFA', detail: 'Add a second layer of protection to every account.' },
  { title: 'Hide Public Email', detail: 'Reduce the chance of targeted phishing attempts.' },
  { title: 'Review Social Privacy Settings', detail: 'Limit profile details to trusted connections.' },
  { title: 'Avoid Public Data Exposure', detail: 'Remove identifiers that are not essential to share.' },
]

const THREAT_SUMMARIES = {
  LOW: {
    title: 'Low Exposure',
    detail: 'Few public signals were discovered. Continue reviewing new profiles before sharing sensitive details.',
  },
  MEDIUM: {
    title: 'Moderate Exposure',
    detail: 'Several public signals are connected to this identity. Strengthen account security and reduce unnecessary visibility.',
  },
  HIGH: {
    title: 'High Exposure',
    detail: 'This identity has a broad public footprint. Prioritize MFA, privacy reviews, and removal of redundant identifiers.',
  },
  CRITICAL: {
    title: 'Critical Exposure',
    detail: 'A very broad footprint is visible. Treat this identity as high priority for account hardening and exposure reduction.',
  },
}

function AnimatedMetric({ value, label, tone }) {
  const numericValue = typeof value === 'number' ? value : null
  const [displayValue, setDisplayValue] = useState(numericValue === null ? value : 0)

  useEffect(() => {
    if (numericValue === null) return undefined
    const start = window.performance.now()
    const duration = 650
    let frame
    function animate(now) {
      const progress = Math.min((now - start) / duration, 1)
      setDisplayValue(Math.round(numericValue * progress))
      if (progress < 1) frame = window.requestAnimationFrame(animate)
    }
    frame = window.requestAnimationFrame(animate)
    return () => window.cancelAnimationFrame(frame)
  }, [numericValue])

  return (
    <div className={`exposure-metric exposure-metric-${tone}`}>
      <strong>{displayValue}</strong>
      <span>{label}</span>
    </div>
  )
}

function RiskMeter({ score, level }) {
  const [displayScore, setDisplayScore] = useState(0)
  const circumference = 2 * Math.PI * 50
  const tone = level === 'HIGH' ? 'risk-high' : level === 'MEDIUM' ? 'risk-medium' : 'risk-low'
  useEffect(() => {
    const start = window.performance.now()
    const duration = 1200
    let frame
    function animate(now) {
      const progress = Math.min((now - start) / duration, 1)
      const eased = 1 - ((1 - progress) ** 3)
      setDisplayScore(Math.round(score * eased))
      if (progress < 1) frame = window.requestAnimationFrame(animate)
    }
    frame = window.requestAnimationFrame(animate)
    return () => window.cancelAnimationFrame(frame)
  }, [score])

  return (
    <div className={`risk-meter-wrap ${tone}`}>
      <div className="risk-meter-glow" />
      <svg viewBox="0 0 120 120" className="risk-meter-svg" aria-label={`${displayScore} out of 100 risk score`}>
        <circle className="risk-meter-track" cx="60" cy="60" r="50" />
        <circle
          className="risk-meter-progress"
          cx="60"
          cy="60"
          r="50"
          strokeDasharray={circumference}
          strokeDashoffset={circumference - (circumference * displayScore) / 100}
        />
      </svg>
      <div className="risk-meter-value">
        <strong>{displayScore}</strong>
        <span>/ 100</span>
      </div>
    </div>
  )
}

export default function ResultsPage() {
  const { state } = useLocation()
  const result = state?.result
  const [downloading, setDownloading] = useState(false)
  const [downloadError, setDownloadError] = useState('')
  const [copiedPlatform, setCopiedPlatform] = useState('')
  const [scanTimestamp] = useState(() => new Intl.DateTimeFormat([], {
    dateStyle: 'medium',
    timeStyle: 'short',
  }).format(new Date()))

  if (!result) return <Navigate to="/" replace />

  const found = PLATFORMS.filter((platform) => result[platform])
  const missing = PLATFORMS.filter((platform) => !result[platform])
  const riskLevel = result.risk_level?.toUpperCase() ?? 'UNKNOWN'
  const threatKey = result.risk_score >= 80 ? 'CRITICAL' : riskLevel
  const threat = THREAT_SUMMARIES[threatKey] ?? THREAT_SUMMARIES.LOW
  const recommendations = result.recommendations?.length
    ? result.recommendations.map((detail) => ({ title: detail, detail: 'Recommended privacy action for this exposure profile.' }))
    : FALLBACK_RECOMMENDATIONS
  const previousScore = result.previous_risk_score ?? state?.previousScore
  const exposureChange = typeof previousScore === 'number' ? result.risk_score - previousScore : null
  const scoreBreakdown = found.map((platform) => ({
    label: `${PLATFORM_LABELS[platform]} Profile Found`,
    value: PLATFORM_WEIGHTS[platform],
  }))
  const hasProfessionalSignal = result.linkedin
  const hasSocialSignal = ['reddit', 'twitter', 'instagram', 'facebook', 'threads'].some((platform) => result[platform])
  const hasDeveloperSignal = result.github
  const hasContentSignal = result.youtube || result.tiktok
  if (hasProfessionalSignal && hasSocialSignal) scoreBreakdown.push({ label: 'Professional + social exposure', value: 5 })
  if (hasDeveloperSignal && hasContentSignal) scoreBreakdown.push({ label: 'Developer + content exposure', value: 5 })
  const scoreBreakdownTotal = scoreBreakdown.reduce((total, item) => total + item.value, 0)
  if (scoreBreakdownTotal !== result.risk_score) {
    scoreBreakdown.push({ label: 'Risk score normalization', value: result.risk_score - scoreBreakdownTotal })
  }

  async function handleCopy(url, platform) {
    await navigator.clipboard.writeText(url)
    setCopiedPlatform(platform)
    window.setTimeout(() => setCopiedPlatform(''), 1600)
  }

  async function handleDownload() {
    setDownloading(true)
    setDownloadError('')
    try {
      const pdf = await downloadReport(result.report_id ?? result.username, Boolean(result.report_id))
      const url = URL.createObjectURL(pdf)
      const link = document.createElement('a')
      link.href = url
      link.download = `ghost-profile-${result.username}.pdf`
      link.click()
      URL.revokeObjectURL(url)
    } catch (error) {
      setDownloadError(getApiErrorMessage(error))
    } finally {
      setDownloading(false)
    }
  }

  return (
    <div className="app-shell results-shell">
      <TopBar showScanAgain />
      <main className="mx-auto w-full max-w-6xl px-5 pb-20 sm:px-8">
        <section className="results-hero">
          <div>
            <p className="section-kicker">ghost intelligence / scan report</p>
            <h1 className="results-title">Identity <span className="text-gradient">exposure</span></h1>
            <p className="results-subtitle">A privacy-first analysis of the public footprint connected to this identity.</p>
          </div>
          <div className="scan-meta glass-card">
            <div><span>Username</span><strong>@{result.username}</strong></div>
            <div><span>Scan status</span><strong className="scan-status"><i /> Complete</strong></div>
            <div><span>Generated time</span><strong>{scanTimestamp}</strong></div>
            <div><span>Report ID</span><strong>{result.report_id ?? 'Pending'}</strong></div>
            <div><span>Risk level</span><strong>{riskLevel}</strong></div>
            <div><span>Privacy grade</span><strong>{result.privacy_grade ?? 'N/A'}</strong></div>
          </div>
        </section>

        <section className="risk-overview glass-card">
          <div className="risk-copy">
            <p className="section-kicker">01 / risk overview</p>
            <h2 className="section-title mt-3">Your digital exposure level</h2>
            <p className="mt-3 max-w-md text-sm leading-6 text-slate-400">
              We found {found.length} of {PLATFORMS.length} monitored platforms connected to this username.
              Review the recommendations below to reduce your public attack surface.
            </p>
            <div className={`risk-label ${riskLevel === 'HIGH' ? 'risk-high-text' : riskLevel === 'MEDIUM' ? 'risk-medium-text' : 'risk-low-text'}`}>
              <span className="h-2 w-2 rounded-full bg-current shadow-[0_0_12px_currentColor]" />
              {riskLevel} RISK
            </div>
            <div className="grade-badge"><span>Privacy grade</span><strong>{result.privacy_grade ?? 'N/A'}</strong></div>
            <div className="score-breakdown">
              <div className="score-breakdown-heading"><span>Why this score?</span><strong>{result.risk_score} total</strong></div>
              {scoreBreakdown.length ? scoreBreakdown.map((item) => (
                <div className="score-breakdown-row" key={item.label}><span>{item.value >= 0 ? '+' : ''}{String(item.value).padStart(2, '0')} {item.label}</span><b>{item.value}</b></div>
              )) : <p className="score-breakdown-empty">No public signals contributed to this score.</p>}
            </div>
          </div>
          <RiskMeter score={result.risk_score} level={riskLevel} />
        </section>

        <section className="results-section">
          <div className="results-section-heading">
            <div><p className="section-kicker">02 / platform analysis</p><h2 className="section-title mt-2">Identity signal map</h2></div>
            <span className="section-count">{found.length} found <b>·</b> {missing.length} not found</span>
          </div>
          {!found.length && (
            <div className="empty-detection-state">
              <strong>No public profiles were identified across monitored services.</strong>
              <p>This may indicate a limited digital footprint.</p>
            </div>
          )}
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {PLATFORMS.map((platform, index) => (
            <PlatformCard key={platform} platform={platform} username={result.username} present={result[platform]} onCopy={handleCopy} copied={copiedPlatform === platform} index={index} />
            ))}
          </div>
        </section>

        <section className="results-lower-grid">
          <div className="glass-card summary-card">
            <p className="section-kicker">03 / exposure summary</p>
            <h2 className="section-title mt-2">Surface area at a glance</h2>
            <div className="summary-metrics">
              <AnimatedMetric value={found.length} label="Platforms found" tone="found" />
              <AnimatedMetric value={missing.length} label="Platforms missing" tone="missing" />
              <AnimatedMetric value={PLATFORMS.length} label="Total platforms" tone="total" />
              <AnimatedMetric value={riskLevel} label="Risk rating" tone="risk" />
            </div>
            <p className="summary-note">Every public profile is a potential signal. Keep only the information you intend to be discoverable.</p>
          </div>
          <div className="glass-card threat-card">
            <p className="section-kicker">04 / intelligence summary</p>
            <h2 className="section-title mt-2">Executive intelligence summary</h2>
            <div className={`threat-callout threat-callout-${riskLevel.toLowerCase()}`}>
              <span className="threat-pulse" />
              <div><strong>{threat.title}</strong><p>{result.insight || threat.detail}</p></div>
            </div>
          </div>
          <div className="glass-card recommendations-card">
            <p className="section-kicker">05 / security recommendations</p>
            <h2 className="section-title mt-2">Harden your presence</h2>
            <div className="recommendation-grid">
              {recommendations.map(({ title, detail }) => (
                <div className="recommendation-card" key={title}>
                  <span className="recommendation-icon">✓</span>
                  <div><strong>{title}</strong><p>{detail}</p></div>
                </div>
              ))}
            </div>
          </div>
        </section>

        <ExposureCharts found={found.length} missing={missing.length} categories={result.category_exposure ?? {}} />
        <section className="insight-row">
          <div className="glass-card insight-card"><p className="section-kicker">09 / OSINT insight engine</p><h2 className="section-title mt-2">Signal interpretation</h2><p>{result.insight || threat.detail}</p></div>
          <div className="glass-card insight-card"><p className="section-kicker">10 / exposure trend</p><h2 className="section-title mt-2">Change since previous scan</h2><strong className={`trend-value ${exposureChange > 0 ? 'trend-up' : 'trend-down'}`}>{exposureChange === null ? '—' : `${exposureChange > 0 ? '+' : ''}${exposureChange}`}</strong><p>{previousScore === undefined ? 'Run another scan to compare exposure over time.' : `Previous: ${previousScore} · Current: ${result.risk_score}`}</p></div>
        </section>
        <SystemStatusPanel />

        <section className="action-panel">
          <div><p className="section-kicker">06 / next action</p><h2 className="section-title mt-2">Keep your identity in your control.</h2></div>
          <div className="action-buttons">
            <button type="button" onClick={handleDownload} disabled={downloading} className="button-primary report-button">
              {downloading ? <><span className="spinner" /> generating...</> : <>download PDF report <span>↓</span></>}
            </button>
          </div>
        </section>
        {downloadError && <p className="mt-4 text-right text-sm text-rose-300" role="alert">{downloadError}</p>}
      </main>
      <footer className="results-footer">Ghost Intelligence Platform v4.0 <span>·</span> Powered by Public OSINT Analysis</footer>
    </div>
  )
}
