import { useEffect, useState } from 'react'
import TopBar from '../components/TopBar'
import ScanForm from '../components/ScanForm'
import SystemStatusPanel from '../components/SystemStatusPanel'

const TYPEWRITER_WORDS = ['username', 'identity', 'profile', 'handle', 'alias']

function useTypewriter(words) {
  const [wordIndex, setWordIndex] = useState(0)
  const [text, setText] = useState('')
  const [isDeleting, setIsDeleting] = useState(false)

  useEffect(() => {
    const word = words[wordIndex]
    const isComplete = text === word
    const isEmpty = text === ''
    const delay = isComplete && !isDeleting ? 1400 : isEmpty && isDeleting ? 350 : isDeleting ? 55 : 95

    const timer = window.setTimeout(() => {
      if (isComplete && !isDeleting) {
        setIsDeleting(true)
        return
      }

      if (isEmpty && isDeleting) {
        setIsDeleting(false)
        setWordIndex((currentIndex) => (currentIndex + 1) % words.length)
        return
      }

      setText((currentText) => (
        isDeleting
          ? currentText.slice(0, -1)
          : word.slice(0, currentText.length + 1)
      ))
    }, delay)

    return () => window.clearTimeout(timer)
  }, [isDeleting, text, wordIndex, words])

  return text
}

export default function HomePage() {
  const typedWord = useTypewriter(TYPEWRITER_WORDS)

  return (
    <div className="app-shell">
      <TopBar />
      <main className="relative mx-auto flex min-h-[calc(100vh-84px)] w-full max-w-6xl items-center px-5 pb-12 pt-4 sm:px-8 sm:pt-0">
        <div className="grid-bg pointer-events-none absolute inset-0 opacity-50" />
        <div className="cyber-particles pointer-events-none absolute inset-0" aria-hidden="true">
          <span /><span /><span /><span /><span />
        </div>
        <div className="home-hero-grid relative w-full">
          <section className="home-scan-hero relative z-10 flex max-w-2xl flex-col items-start text-left">
            <div className="mb-5 inline-flex items-center gap-2 rounded-full border border-cyan/20 bg-cyan/[0.06] px-3 py-1.5 font-mono text-[10px] uppercase tracking-[0.2em] text-cyan">
              <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-cyan shadow-[0_0_10px_#41d9ff]" /> OSINT Intelligence Platform
            </div>
            <h1
              className="hero-headline max-w-2xl text-5xl font-semibold leading-[0.96] tracking-[-0.06em] text-white sm:text-7xl"
              aria-label="Find the ghost behind a username."
            >
              Find the <span className="text-gradient">ghost</span> behind a{' '}
              <span className="typewriter-word text-gradient" aria-hidden="true">
                {typedWord}
                <span className="typewriter-cursor" />
              </span>.
            </h1>
            <p className="home-hero-description mt-6 max-w-xl text-sm leading-6 text-slate-400 sm:text-base">
              Turn scattered signals into a clear, privacy-first intelligence brief.
            </p>
            <div className="home-scan-form mt-7 w-full"><ScanForm /></div>
          </section>
          <aside className="home-visual-rail" aria-label="Live cyber intelligence visualization">
          <div className="cyber-visual radar-visual-frame relative" aria-label="Live cyber intelligence visualization">
            <div className="visual-status">
              <span className="visual-status-dot" />
              intelligence online
            </div>
            <div className="cyber-radar home-radar-scale radar-canvas absolute bottom-0 left-0">
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
          <SystemStatusPanel />
          </aside>
        </div>
      </main>
    </div>
  )
}
