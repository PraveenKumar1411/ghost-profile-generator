import { Link } from 'react-router-dom'
import { ExternalLink, History, RefreshCw } from 'lucide-react'
import Logo from './Logo'

export default function TopBar({ showScanAgain = false, showHistory = true }) {
  return (
    <header className="topbar-shell relative z-20 mx-auto flex items-center justify-between py-5">
      <Link to="/" aria-label="Ghost Profile Generator home" className="rounded-2xl transition-opacity hover:opacity-90">
        <Logo />
      </Link>
      <nav className={showScanAgain ? 'topbar-actions' : undefined} aria-label="Primary navigation">
        {showScanAgain && (
          <Link to="/" className="topbar-scan-again">
            <RefreshCw className="topbar-scan-again-icon" aria-hidden="true" />
            <span className="topbar-scan-again-copy"><span>SCAN</span> <strong>AGAIN</strong></span>
            <span className="topbar-scan-again-arrow" aria-hidden="true"><ExternalLink /></span>
          </Link>
        )}
        {showHistory && (
          <Link to="/history" className="topbar-nav-link" aria-label="Open scan history">
            <span className="topbar-nav-leading">
              <History className="topbar-nav-icon" aria-hidden="true" />
              <span className="topbar-nav-divider" aria-hidden="true" />
              <span className="topbar-nav-status" aria-hidden="true" />
            </span>
            <span className="topbar-nav-copy"><span>SCAN</span> <strong>HISTORY</strong></span>
            <span className="topbar-nav-arrow" aria-hidden="true"><ExternalLink /></span>
          </Link>
        )}
      </nav>
    </header>
  )
}
