import { useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { getApiErrorMessage, getScanResult, getScanStatus, startScan } from '../services/scanApi'
import ScanProgress from './ScanProgress'

const USERNAME_PATTERN = /^[A-Za-z0-9_][A-Za-z0-9_.-]{0,38}$/

export default function ScanForm() {
  const navigate = useNavigate()
  const [username, setUsername] = useState('')
  const [error, setError] = useState('')
  const [status, setStatus] = useState('idle')
  const [job, setJob] = useState(null)
  const scanAttemptRef = useRef(0)
  const loading = status === 'loading'

  async function handleSubmit(event) {
    event.preventDefault()
    const value = username.trim()
    if (!value) return setError('Enter a username to begin the scan.')
    if (!USERNAME_PATTERN.test(value)) {
      return setError('Use 1–39 letters, numbers, underscores, periods, or hyphens.')
    }

    setError('')
    setStatus('loading')
    const scanAttempt = scanAttemptRef.current
    try {
      const started = await startScan(value)
      if (scanAttempt !== scanAttemptRef.current) return
      setJob({ scanId: started.scan_id, progress: 0, status: started.status })
      const result = await waitForScan(started.scan_id, scanAttempt)
      if (result === null) return
      setStatus('success')
      window.setTimeout(() => navigate('/results', { state: { result } }), 450)
    } catch (requestError) {
      if (scanAttempt !== scanAttemptRef.current) return
      setError(getApiErrorMessage(requestError))
      setStatus('idle')
    }

    async function waitForScan(scanId, attempt) {
      while (true) {
        if (attempt !== scanAttemptRef.current) return null
        const snapshot = await getScanStatus(scanId)
        if (attempt !== scanAttemptRef.current) return null
        setJob({ ...snapshot, scanId })
        if (snapshot.status === 'failed') {
          throw new Error(snapshot.failure_reason || 'The background scan failed.')
        }
        if (snapshot.status === 'completed') {
          return getScanResult(scanId)
        }
        await new Promise((resolve) => window.setTimeout(resolve, 2000))
      }
    }
  }

  function handleCancel() {
    scanAttemptRef.current += 1
    setStatus('idle')
    setJob(null)
    setError('')
  }

  return (
    <form onSubmit={handleSubmit} className="w-full max-w-xl">
      <label htmlFor="username" className="mb-3 block font-mono text-xs uppercase tracking-[0.18em] text-slate-400">
        Username / email handle
      </label>
      <div className="scan-shell group flex flex-col gap-3 rounded-2xl border border-white/10 bg-white/[0.04] p-2 transition focus-within:border-cyan/50 focus-within:bg-cyan/[0.04]">
        <div className="flex flex-1 items-center px-3">
          <span className="mr-2 font-mono text-cyan">@</span>
          <input
            id="username"
            value={username}
            onChange={(event) => { setUsername(event.target.value); setError('') }}
            placeholder="e.g. johndoe123"
            maxLength={39}
            autoComplete="off"
            aria-invalid={Boolean(error)}
            aria-describedby={error ? 'scan-error' : undefined}
            className="w-full bg-transparent py-3 text-base text-slate-100 outline-none placeholder:text-slate-600"
          />
        </div>
      </div>
      <div className="scan-actions mt-2">
        <button type="button" disabled={!loading} className="scan-cancel-button" onClick={handleCancel}>
          <span aria-hidden="true">✕</span> cancel
        </button>
        <button type="submit" disabled={loading || status === 'success'} className="button-primary scan-submit-button">
          {loading ? <><span className="spinner" /> scanning...</> : status === 'success' ? <>scan complete <span aria-hidden="true">✓</span></> : job?.status === 'failed' ? <>retry scan <span aria-hidden="true">↻</span></> : <>scan identity <span aria-hidden="true">→</span></>}
        </button>
      </div>
      <div id="scan-error" className="mt-2 min-h-5 text-sm text-rose-300" role="alert">{error}</div>
      {job?.status === 'failed' && (
        <div className="mt-2 flex items-center justify-between gap-3 rounded-xl border border-rose-400/20 bg-rose-400/[0.06] px-3 py-2 text-xs text-rose-200">
          <span>Scan failed. You can retry this identity.</span>
          <button type="button" className="font-mono text-[10px] uppercase tracking-wider text-rose-300 hover:text-white" onClick={() => { setJob(null); setError(''); setStatus('idle') }}>
            Retry
          </button>
        </div>
      )}
      <ScanProgress
        active={loading}
        complete={status === 'success'}
        progress={job?.progress}
        scanId={job?.scanId}
        currentPlatform={job?.current_platform}
        completedPlatforms={job?.completed_platforms}
        remainingPlatforms={job?.remaining_platforms}
      />
    </form>
  )
}
