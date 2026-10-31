import { Link } from 'react-router-dom'
import { FaHistory } from 'react-icons/fa'
import Logo from './Logo'

export default function TopBar() {
  return (
    <header className="topbar-shell relative z-20 mx-auto flex items-center justify-between py-5">
      <Link to="/" aria-label="Ghost Profile Generator home" className="rounded-2xl transition-opacity hover:opacity-90">
        <Logo />
      </Link>
      <nav aria-label="Primary navigation">
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
