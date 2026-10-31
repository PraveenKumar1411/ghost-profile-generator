import { useEffect, useState } from 'react'

const SCAN_STAGES = [
  'Initializing Scan...',
  'Checking Public Signals...',
  'Analyzing Exposure...',
  'Generating Intelligence Report...',
]

export default function ScanProgress({
  active,
  complete = false,
  progress: reportedProgress,
  scanId,
  currentPlatform,
  completedPlatforms = [],
  remainingPlatforms = [],
}) {
  const [simulatedProgress, setSimulatedProgress] = useState(0)
  const progress = typeof reportedProgress === 'number' ? reportedProgress : simulatedProgress

  useEffect(() => {
    if (!active && !complete) {
      setSimulatedProgress(0)
      return undefined
    }

    if (complete) {
      setSimulatedProgress(100)
      return undefined
    }

    const timer = window.setInterval(() => {
      setSimulatedProgress((current) => {
        if (current >= 92) return current
        const increment = current < 30 ? 3 : current < 65 ? 2 : 1
        return Math.min(current + increment, 92)
      })
    }, 180)

    return () => window.clearInterval(timer)
  }, [active, complete])

  if (!active && !complete) return null

  const stageIndex = complete
    ? SCAN_STAGES.length - 1
    : Math.min(Math.floor(progress / 25), SCAN_STAGES.length - 1)
  const stage = complete ? SCAN_STAGES[SCAN_STAGES.length - 1] : SCAN_STAGES[stageIndex]

  return (
    <section
      className="mt-4 overflow-hidden rounded-2xl border border-cyan-400/20 bg-slate-950/70 p-4 shadow-[0_0_30px_rgba(65,217,255,0.08)] backdrop-blur-xl sm:p-5"
      aria-label="Scan progress"
      aria-live="polite"
    >
      <div className="flex items-start justify-between gap-4">
        <div className="flex min-w-0 items-center gap-3">
          <span className="relative flex h-3 w-3 shrink-0">
            <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-cyan-400 opacity-60" />
            <span className="relative inline-flex h-3 w-3 rounded-full bg-cyan-300 shadow-[0_0_14px_#41d9ff]" />
          </span>
          <div className="min-w-0">
            <p className="truncate font-mono text-[10px] uppercase tracking-[0.18em] text-cyan-300">
              {stage}
            </p>
            <p className="mt-1 text-xs text-slate-500">
              {currentPlatform
                ? `Current platform: ${currentPlatform}`
                : scanId
                  ? `Scan ID: ${scanId}`
                  : 'Mapping public identity signals across monitored platforms'}
            </p>
          </div>

          {scanId && (
            <div className="mt-3 flex flex-wrap gap-x-4 gap-y-1 font-mono text-[9px] uppercase tracking-wider text-slate-500">
              <span><b className="text-cyan-300">{completedPlatforms.length}</b> completed</span>
              <span><b className="text-violet-300">{remainingPlatforms.length}</b> remaining</span>
              {currentPlatform && <span>active: <b className="text-slate-300">{currentPlatform}</b></span>}
            </div>
          )}
        </div>
        <strong className="shrink-0 font-mono text-lg text-cyan-300">
          {progress}%
        </strong>
      </div>

      <div
        className="mt-4 h-2 overflow-hidden rounded-full bg-slate-950/80"
        role="progressbar"
        aria-valuemin="0"
        aria-valuemax="100"
        aria-valuenow={progress}
        aria-valuetext={`${progress}% complete`}
      >
        <div
          className="relative h-full rounded-full bg-[linear-gradient(90deg,#10B981_0%,#34D399_50%,#6EE7B7_100%)] shadow-[0_0_12px_rgba(16,185,129,.35),0_0_30px_rgba(16,185,129,.20)] transition-[width] duration-300 ease-out"
          style={{ width: `${progress}%` }}
        >
          <span className="absolute inset-y-0 right-0 w-16 animate-pulse bg-white/50 blur-sm" />
        </div>
      </div>

      <div className="mt-3 grid grid-cols-2 gap-2 sm:grid-cols-4">
        {SCAN_STAGES.map((scanStage, index) => {
          const reached = complete || index <= stageIndex
          return (
            <div
              key={scanStage}
              className={`flex items-center gap-1.5 font-mono text-[9px] uppercase tracking-wider transition-colors ${
                reached ? 'text-cyan-300' : 'text-slate-600'
              }`}
            >
              <span className={`h-1.5 w-1.5 rounded-full ${reached ? 'bg-cyan-300 shadow-[0_0_8px_#41d9ff]' : 'bg-slate-700'}`} />
              <span>{index + 1}</span>
            </div>
          )
        })}
      </div>
    </section>
  )
}
