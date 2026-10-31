import { Link } from 'react-router-dom'
import { FaHistory } from 'react-icons/fa'
import Logo from './Logo'

export default function TopBar({ showScanAgain = false }) {
  return (
    <header className="topbar-shell relative z-20 mx-auto flex items-center justify-between py-5">
      <Link to="/" aria-label="Ghost Profile Generator home" className="rounded-2xl transition-opacity hover:opacity-90">
        <Logo />
      </Link>
      <nav className={showScanAgain ? 'topbar-actions' : undefined} aria-label="Primary navigation">
        {showScanAgain && (
          <Link to="/" className="topbar-scan-again">
            <span>SCAN AGAIN</span>
            <span aria-hidden="true">↗</span>
          </Link>
        )}
        <Link to="/history" className="topbar-nav-link">
          <FaHistory className="topbar-nav-icon" aria-hidden="true" />
          <span className="topbar-nav-status" aria-hidden="true" />
          <span>SCAN HISTORY</span>
          <span className="topbar-nav-arrow" aria-hidden="true">↗</span>
        </Link>
      </nav>
    </header>
  )
}
