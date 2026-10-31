import TopBar from '../components/TopBar'
import ScanForm from '../components/ScanForm'

export default function HomePage() {
  return (
    <div className="app-shell">
      <TopBar />
      <main className="relative mx-auto flex min-h-[calc(100vh-84px)] w-full max-w-6xl items-center px-5 pb-12 pt-4 sm:px-8 sm:pt-0">
        <div className="grid-bg pointer-events-none absolute inset-0 opacity-50" />
        <div className="cyber-particles pointer-events-none absolute inset-0" aria-hidden="true">
          <span /><span /><span /><span /><span />
        </div>
        <div className="relative grid w-full items-center gap-14 lg:grid-cols-[1.05fr_0.95fr]">
          <section className="relative z-10">
            <div className="mb-6 inline-flex items-center gap-2 rounded-full border border-cyan/20 bg-cyan/[0.06] px-3 py-1.5 font-mono text-[10px] uppercase tracking-[0.2em] text-cyan">
              <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-cyan shadow-[0_0_10px_#41d9ff]" /> OSINT intelligence platform
            </div>
            <h1 className="hero-headline max-w-3xl text-5xl font-semibold leading-[0.96] tracking-[-0.06em] text-white sm:text-7xl">
              Find the <span className="text-gradient">ghost</span><br className="hidden sm:block" /> behind a username.
            </h1>
            <div className="mt-6"><ScanForm /></div>
            <p className="mt-4 max-w-lg text-sm leading-6 text-slate-400 sm:text-base">
              Map public profiles across the internet. Turn scattered signals into a clear, privacy-first intelligence brief.
            </p>
            <div className="mt-5 flex flex-wrap gap-2.5">
              {['OSINT powered', 'Privacy focused', 'Cybersecurity intelligence'].map((item) => (
                <span key={item} className="trust-badge"><span>✓</span>{item}</span>
              ))}
            </div>
            <p className="mt-5 font-mono text-[10px] uppercase tracking-widest text-slate-600">encrypted request · no data stored</p>
          </section>
          <div className="cyber-visual relative mx-auto hidden h-[29rem] w-[25rem] lg:block" aria-label="Live cyber intelligence visualization">
            <div className="visual-status">
              <span className="visual-status-dot" />
              intelligence online
            </div>
            <div className="cyber-radar absolute bottom-0 left-0 h-[25rem] w-[25rem]">
            <div className="radar-scan" />
            <div className="radar-ring ring-one" /><div className="radar-ring ring-two" /><div className="radar-ring ring-three" />
            <div className="radar-crosshair" />
            <div className="radar-node node-one" /><div className="radar-node node-two" /><div className="radar-node node-three" /><div className="radar-node node-four" />
            <div className="radar-link link-one" /><div className="radar-link link-two" /><div className="radar-link link-three" />
            <div className="radar-core" aria-label="Identity beacon active">
              <div className="identity-beacon"><span /></div>
              <span className="absolute -bottom-9 whitespace-nowrap font-mono text-[9px] uppercase tracking-[0.24em] text-cyan/70">identity signal detected</span>
            </div>
            <span className="absolute -left-4 top-1/2 font-mono text-[9px] text-slate-600">TRACE / 01</span>
            <span className="absolute -right-4 top-1/4 font-mono text-[9px] text-cyan/60">LIVE SCAN</span>
            <span className="absolute bottom-1 right-6 font-mono text-[9px] text-violet-300/60">NODES: 10</span>
            </div>
          </div>
        </div>
      </main>
    </div>
  )
}
