export default function Logo({ compact = false }) {
  return (
    <div className="flex items-center gap-3">
      <img src="/ghost-logo.png" alt="Ghost Profile Generator" className="h-12 w-12 rounded-xl object-contain drop-shadow-[0_0_14px_rgba(65,217,255,0.35)]" />
      {!compact && (
        <div>
          <p className="text-sm font-semibold tracking-tight text-slate-100">GHOST<span className="text-cyan">.</span></p>
          <p className="mt-0.5 font-mono text-[9px] uppercase tracking-[0.22em] text-slate-500">profile generator</p>
        </div>
      )}
    </div>
  )
}
