import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { getApiErrorMessage, scanUsername } from '../services/scanApi'

const USERNAME_PATTERN = /^[A-Za-z0-9_][A-Za-z0-9_.-]{0,38}$/

export default function ScanForm() {
  const navigate = useNavigate()
  const [username, setUsername] = useState('')
  const [error, setError] = useState('')
  const [status, setStatus] = useState('idle')
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
    try {
      const result = await scanUsername(value)
      setStatus('success')
      window.setTimeout(() => navigate('/results', { state: { result } }), 450)
    } catch (requestError) {
      setError(getApiErrorMessage(requestError))
      setStatus('idle')
    }
  }

  return (
    <form onSubmit={handleSubmit} className="w-full max-w-xl">
      <label htmlFor="username" className="mb-3 block font-mono text-xs uppercase tracking-[0.18em] text-slate-400">
        Username / email handle
      </label>
      <div className="scan-shell group flex flex-col gap-3 rounded-2xl border border-white/10 bg-white/[0.04] p-2 transition focus-within:border-cyan/50 focus-within:bg-cyan/[0.04] sm:flex-row">
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
        <button type="submit" disabled={loading || status === 'success'} className="button-primary min-w-40">
          {loading ? <><span className="spinner" /> scanning...</> : status === 'success' ? <>scan complete <span aria-hidden="true">✓</span></> : <>scan identity <span aria-hidden="true">→</span></>}
        </button>
      </div>
      <div id="scan-error" className="mt-3 min-h-5 text-sm text-rose-300" role="alert">{error}</div>
      {loading && (
        <div className="scan-skeleton" aria-label="Preparing intelligence report" aria-live="polite">
          <span className="scan-skeleton-line scan-skeleton-line-wide" />
          <span className="scan-skeleton-line" />
          <span className="scan-skeleton-line scan-skeleton-line-short" />
        </div>
      )}
    </form>
  )
}
