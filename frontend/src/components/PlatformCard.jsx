const PLATFORM_META = {
  github: { label: 'GitHub', mark: 'GH' },
  reddit: { label: 'Reddit', mark: 'R' },
  twitter: { label: 'Twitter / X', mark: 'X' },
  instagram: { label: 'Instagram', mark: 'IG' },
  linkedin: { label: 'LinkedIn', mark: 'in' },
}

export default function PlatformCard({ platform, present, index = 0 }) {
  const meta = PLATFORM_META[platform]
  return (
    <article className={`platform-card glass-card flex items-center justify-between p-5 ${present ? 'platform-card-found' : ''}`} style={{ '--card-delay': `${index * 70}ms` }}>
      <div className="flex items-center gap-4">
        <div className="platform-mark grid h-11 w-11 place-items-center rounded-xl border border-white/10 bg-white/[0.05] font-mono text-xs font-bold text-slate-300">{meta.mark}</div>
        <div>
          <h3 className="font-medium text-slate-100">{meta.label}</h3>
          <p className="mt-1 font-mono text-[10px] uppercase tracking-wider text-slate-500">{present ? 'public signal detected' : 'no public signal found'}</p>
        </div>
      </div>
      <span className={`status-pill ${present ? 'status-found' : 'status-clear'}`}>
        <span className="h-1.5 w-1.5 rounded-full bg-current" /> {present ? '✅ Found' : '❌ Not Found'}
      </span>
    </article>
  )
}
